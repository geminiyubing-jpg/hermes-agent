"""Main FeishuAdapter class that composes all Mixins into a single adapter.

This is the primary entry-point for the Feishu platform adapter.  It inherits
from every focused Mixin (media, batch, webhook, websocket, card_handler) and
from :class:`BasePlatformAdapter`, then adds lifecycle, settings, inbound-event
routing, outbound send pipeline, and QR-onboarding methods that do not belong
in any single mixin.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import itertools
import json
import logging
import mimetypes
import os
import re
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

# ---------------------------------------------------------------------------
# Optional dependencies — must be imported *before* lark_oapi so they remain
# available for tests and webhook mode even if the SDK is missing.
# ---------------------------------------------------------------------------

try:
    import aiohttp
    from aiohttp import web
except ImportError:
    aiohttp = None  # type: ignore[assignment]
    web = None  # type: ignore[assignment]

try:
    import websockets  # noqa: F401 — availability flag
except ImportError:
    websockets = None  # type: ignore[assignment]

try:
    import lark_oapi as lark
    from lark_oapi.api.application.v6 import GetApplicationRequest
    from lark_oapi.api.im.v1 import (
        CreateFileRequest,
        CreateFileRequestBody,
        CreateImageRequest,
        CreateImageRequestBody,
        CreateMessageRequest,
        CreateMessageRequestBody,
        GetChatRequest,
        GetMessageRequest,
        GetMessageResourceRequest,
        P2ImMessageMessageReadV1,
        ReplyMessageRequest,
        ReplyMessageRequestBody,
        UpdateMessageRequest,
        UpdateMessageRequestBody,
    )
    from lark_oapi.core.const import FEISHU_DOMAIN, LARK_DOMAIN
    from lark_oapi.event.callback.model.p2_card_action_trigger import (
        CallBackCard,
        P2CardActionTriggerResponse,
    )
    from lark_oapi.event.dispatcher_handler import EventDispatcherHandler
    from lark_oapi.ws import Client as FeishuWSClient

    FEISHU_AVAILABLE = True
except ImportError:
    FEISHU_AVAILABLE = False
    lark = None  # type: ignore[assignment]
    CallBackCard = None  # type: ignore[assignment]
    P2CardActionTriggerResponse = None  # type: ignore[assignment]
    EventDispatcherHandler = None  # type: ignore[assignment]
    FeishuWSClient = None  # type: ignore[assignment]
    FEISHU_DOMAIN = None  # type: ignore[assignment]
    LARK_DOMAIN = None  # type: ignore[assignment]

FEISHU_WEBSOCKET_AVAILABLE = websockets is not None
FEISHU_WEBHOOK_AVAILABLE = aiohttp is not None

# ---------------------------------------------------------------------------
# Internal package imports
# ---------------------------------------------------------------------------

from gateway.config import Platform, PlatformConfig
from gateway.platforms.base import (
    BasePlatformAdapter,
    MessageEvent,
    MessageType,
    SendResult,
    SUPPORTED_DOCUMENT_TYPES,
    cache_document_from_bytes,
    cache_image_from_url,
    cache_audio_from_bytes,
    cache_image_from_bytes,
)
from gateway.status import acquire_scoped_lock, release_scoped_lock
from hermes_constants import get_hermes_home

from .media import FeishuMediaMixin
from .batch import FeishuBatchMixin
from .webhook import FeishuWebhookMixin
from .websocket import FeishuWebSocketMixin
from .card_handler import FeishuCardHandlerMixin
from .request_builders import FeishuRequestBuilderMixin

from .constants import (
    _MARKDOWN_HINT_RE,
    _FEISHU_APP_LOCK_SCOPE,
    _FEISHU_ACK_EMOJI,
    _FEISHU_CONNECT_ATTEMPTS,
    _FEISHU_DEDUP_TTL_SECONDS,
    _FEISHU_SEND_ATTEMPTS,
    _FEISHU_SENDER_NAME_TTL_SECONDS,
    _FEISHU_REPLY_FALLBACK_CODES,
    _DEFAULT_DEDUP_CACHE_SIZE,
    _DEFAULT_TEXT_BATCH_DELAY_SECONDS,
    _DEFAULT_TEXT_BATCH_MAX_MESSAGES,
    _DEFAULT_TEXT_BATCH_MAX_CHARS,
    _DEFAULT_MEDIA_BATCH_DELAY_SECONDS,
    _DEFAULT_WEBHOOK_HOST,
    _DEFAULT_WEBHOOK_PORT,
    _DEFAULT_WEBHOOK_PATH,
    _FEISHU_SENDER_NAME_CACHE_MAX,
    _FEISHU_CHAT_INFO_CACHE_MAX,
    _FEISHU_CHAT_INFO_TTL_SECONDS,
    _FEISHU_MESSAGE_TEXT_CACHE_MAX,
)
from .onboarding import (
    _post_registration,
    _init_registration,
    _begin_registration,
    _poll_registration,
    _render_qr,
    probe_bot,
    _probe_bot_sdk,
    qr_register,
    _qrcode_mod,
)
from .types import FeishuAdapterSettings, FeishuGroupRule, FeishuBatchState
from .message_parser import (
    _build_markdown_post_payload,
    _strip_markdown_to_plain_text,
    _coerce_int,
    _coerce_required_int,
    normalize_feishu_message,
)
from .constants import _POST_CONTENT_INVALID_RE, _MARKDOWN_HINT_RE
from .websocket import _run_official_feishu_ws_client  # re-exported for test backward-compat

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def check_feishu_requirements() -> bool:
    """Check if Feishu/Lark dependencies are available."""
    return FEISHU_AVAILABLE


# =========================================================================
#
#                         FeishuAdapter
#
# =========================================================================


class FeishuAdapter(
    FeishuMediaMixin,
    FeishuBatchMixin,
    FeishuWebhookMixin,
    FeishuWebSocketMixin,
    FeishuCardHandlerMixin,
    FeishuRequestBuilderMixin,
    BasePlatformAdapter,
):
    """Feishu/Lark bot adapter."""

    MAX_MESSAGE_LENGTH = 8000
    # Threshold for detecting Feishu client-side message splits.
    # When a chunk is near the ~4096-char practical limit, a continuation
    # is almost certain.
    _SPLIT_THRESHOLD = 4000

    # =========================================================================
    # Lifecycle — init / settings / connect / disconnect
    # =========================================================================

    def __init__(self, config: PlatformConfig):
        super().__init__(config, Platform.FEISHU)

        self._settings = self._load_settings(config.extra or {})
        self._apply_settings(self._settings)
        self._client: Optional[Any] = None
        self._ws_client: Optional[Any] = None
        self._ws_future: Optional[asyncio.Future] = None
        self._ws_thread_loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._webhook_runner: Optional[Any] = None
        self._webhook_site: Optional[Any] = None
        self._event_handler: Optional[Any] = None
        self._seen_message_ids: Dict[str, float] = {}  # message_id -> seen_at (time.time())
        self._seen_message_order: List[str] = []
        self._dedup_state_path = get_hermes_home() / "feishu_seen_message_ids.json"
        self._dedup_lock = threading.Lock()
        self._dedup_dirty = False
        self._dedup_persist_scheduled = False
        self._sender_name_cache: Dict[str, tuple[str, float]] = {}  # sender_id -> (name, expire_at)
        self._webhook_rate_counts: Dict[str, tuple[int, float]] = {}  # rate_key -> (count, window_start)
        self._webhook_anomaly_counts: Dict[str, tuple[int, str, float]] = {}  # ip -> (count, last_status, first_seen)
        self._card_action_tokens: Dict[str, float] = {}  # token -> first_seen_time
        # Inbound events that arrived before the adapter loop was ready
        # (e.g. during startup/restart or network-flap reconnect). A single
        # drainer thread replays them as soon as the loop becomes available.
        self._pending_inbound_events: List[Any] = []
        self._pending_inbound_lock = threading.Lock()
        self._pending_drain_scheduled = False
        self._pending_inbound_max_depth = 1000  # cap queue; drop oldest beyond
        self._chat_locks: Dict[str, asyncio.Lock] = {}  # chat_id -> lock (per-chat serial processing)
        self._sent_message_ids_to_chat: Dict[str, str] = {}  # message_id -> chat_id (for reaction routing)
        self._sent_message_id_order: List[str] = []  # LRU order for _sent_message_ids_to_chat
        self._chat_info_cache: Dict[str, tuple[Dict[str, Any], float]] = {}  # chat_id -> (info, cached_at)
        self._message_text_cache: Dict[str, Optional[str]] = {}
        self._app_lock_identity: Optional[str] = None
        self._text_batch_state = FeishuBatchState()
        self._pending_text_batches = self._text_batch_state.events
        self._pending_text_batch_tasks = self._text_batch_state.tasks
        self._pending_text_batch_counts = self._text_batch_state.counts
        self._media_batch_state = FeishuBatchState()
        self._pending_media_batches = self._media_batch_state.events
        self._pending_media_batch_tasks = self._media_batch_state.tasks
        # Exec approval button state (approval_id -> {session_key, message_id, chat_id})
        self._approval_state: Dict[int, Dict[str, str]] = {}
        self._approval_counter = itertools.count(1)
        self._load_seen_message_ids()

    @staticmethod
    def _load_settings(extra: Dict[str, Any]) -> FeishuAdapterSettings:
        # Parse per-group rules from config
        raw_group_rules = extra.get("group_rules", {})
        group_rules: Dict[str, FeishuGroupRule] = {}
        if isinstance(raw_group_rules, dict):
            for chat_id, rule_cfg in raw_group_rules.items():
                if not isinstance(rule_cfg, dict):
                    continue
                group_rules[str(chat_id)] = FeishuGroupRule(
                    policy=str(rule_cfg.get("policy", "open")).strip().lower(),
                    allowlist=set(str(u).strip() for u in rule_cfg.get("allowlist", []) if str(u).strip()),
                    blacklist=set(str(u).strip() for u in rule_cfg.get("blacklist", []) if str(u).strip()),
                )

        # Bot-level admins
        raw_admins = extra.get("admins", [])
        admins = frozenset(str(u).strip() for u in raw_admins if str(u).strip())

        # Default group policy (for groups not in group_rules)
        default_group_policy = str(extra.get("default_group_policy", "")).strip().lower()

        return FeishuAdapterSettings(
            app_id=str(extra.get("app_id") or os.getenv("FEISHU_APP_ID", "")).strip(),
            app_secret=str(extra.get("app_secret") or os.getenv("FEISHU_APP_SECRET", "")).strip(),
            domain_name=str(extra.get("domain") or os.getenv("FEISHU_DOMAIN", "feishu")).strip().lower(),
            connection_mode=str(
                extra.get("connection_mode") or os.getenv("FEISHU_CONNECTION_MODE", "websocket")
            ).strip().lower(),
            encrypt_key=os.getenv("FEISHU_ENCRYPT_KEY", "").strip(),
            verification_token=os.getenv("FEISHU_VERIFICATION_TOKEN", "").strip(),
            group_policy=os.getenv("FEISHU_GROUP_POLICY", "allowlist").strip().lower(),
            allowed_group_users=frozenset(
                item.strip()
                for item in os.getenv("FEISHU_ALLOWED_USERS", "").split(",")
                if item.strip()
            ),
            bot_open_id=os.getenv("FEISHU_BOT_OPEN_ID", "").strip(),
            bot_user_id=os.getenv("FEISHU_BOT_USER_ID", "").strip(),
            bot_name=os.getenv("FEISHU_BOT_NAME", "").strip(),
            dedup_cache_size=max(
                32,
                int(os.getenv("HERMES_FEISHU_DEDUP_CACHE_SIZE", str(_DEFAULT_DEDUP_CACHE_SIZE))),
            ),
            text_batch_delay_seconds=float(
                os.getenv("HERMES_FEISHU_TEXT_BATCH_DELAY_SECONDS", str(_DEFAULT_TEXT_BATCH_DELAY_SECONDS))
            ),
            text_batch_split_delay_seconds=float(
                os.getenv("HERMES_FEISHU_TEXT_BATCH_SPLIT_DELAY_SECONDS", "2.0")
            ),
            text_batch_max_messages=max(
                1,
                int(os.getenv("HERMES_FEISHU_TEXT_BATCH_MAX_MESSAGES", str(_DEFAULT_TEXT_BATCH_MAX_MESSAGES))),
            ),
            text_batch_max_chars=max(
                1,
                int(os.getenv("HERMES_FEISHU_TEXT_BATCH_MAX_CHARS", str(_DEFAULT_TEXT_BATCH_MAX_CHARS))),
            ),
            media_batch_delay_seconds=float(
                os.getenv("HERMES_FEISHU_MEDIA_BATCH_DELAY_SECONDS", str(_DEFAULT_MEDIA_BATCH_DELAY_SECONDS))
            ),
            webhook_host=str(
                extra.get("webhook_host") or os.getenv("FEISHU_WEBHOOK_HOST", _DEFAULT_WEBHOOK_HOST)
            ).strip(),
            webhook_port=int(
                extra.get("webhook_port") or os.getenv("FEISHU_WEBHOOK_PORT", str(_DEFAULT_WEBHOOK_PORT))
            ),
            webhook_path=(
                str(extra.get("webhook_path") or os.getenv("FEISHU_WEBHOOK_PATH", _DEFAULT_WEBHOOK_PATH)).strip()
                or _DEFAULT_WEBHOOK_PATH
            ),
            ws_reconnect_nonce=_coerce_required_int(extra.get("ws_reconnect_nonce"), default=30, min_value=0),
            ws_reconnect_interval=_coerce_required_int(extra.get("ws_reconnect_interval"), default=120, min_value=1),
            ws_ping_interval=_coerce_int(extra.get("ws_ping_interval"), default=None, min_value=1),
            ws_ping_timeout=_coerce_int(extra.get("ws_ping_timeout"), default=None, min_value=1),
            admins=admins,
            default_group_policy=default_group_policy,
            group_rules=group_rules,
        )

    def _apply_settings(self, settings: FeishuAdapterSettings) -> None:
        self._app_id = settings.app_id
        self._app_secret = settings.app_secret
        self._domain_name = settings.domain_name
        self._connection_mode = settings.connection_mode
        self._encrypt_key = settings.encrypt_key
        self._verification_token = settings.verification_token
        self._group_policy = settings.group_policy
        self._allowed_group_users = set(settings.allowed_group_users)
        self._admins = set(settings.admins)
        self._default_group_policy = settings.default_group_policy or settings.group_policy
        self._group_rules = settings.group_rules
        self._bot_open_id = settings.bot_open_id
        self._bot_user_id = settings.bot_user_id
        self._bot_name = settings.bot_name
        self._dedup_cache_size = settings.dedup_cache_size
        self._text_batch_delay_seconds = settings.text_batch_delay_seconds
        self._text_batch_split_delay_seconds = settings.text_batch_split_delay_seconds
        self._text_batch_max_messages = settings.text_batch_max_messages
        self._text_batch_max_chars = settings.text_batch_max_chars
        self._media_batch_delay_seconds = settings.media_batch_delay_seconds
        self._webhook_host = settings.webhook_host
        self._webhook_port = settings.webhook_port
        self._webhook_path = settings.webhook_path
        self._ws_reconnect_nonce = settings.ws_reconnect_nonce
        self._ws_reconnect_interval = settings.ws_reconnect_interval
        self._ws_ping_interval = settings.ws_ping_interval
        self._ws_ping_timeout = settings.ws_ping_timeout

    def _build_event_handler(self) -> Any:
        if EventDispatcherHandler is None:
            return None
        return (
            EventDispatcherHandler.builder(
                self._encrypt_key,
                self._verification_token,
            )
            .register_p2_im_message_message_read_v1(self._on_message_read_event)
            .register_p2_im_message_receive_v1(self._on_message_event)
            .register_p2_im_message_reaction_created_v1(
                lambda data: self._on_reaction_event("im.message.reaction.created_v1", data)
            )
            .register_p2_im_message_reaction_deleted_v1(
                lambda data: self._on_reaction_event("im.message.reaction.deleted_v1", data)
            )
            .register_p2_card_action_trigger(self._on_card_action_trigger)
            .register_p2_im_chat_member_bot_added_v1(self._on_bot_added_to_chat)
            .register_p2_im_chat_member_bot_deleted_v1(self._on_bot_removed_from_chat)
            .register_p2_im_chat_access_event_bot_p2p_chat_entered_v1(self._on_p2p_chat_entered)
            .register_p2_im_message_recalled_v1(self._on_message_recalled)
            .register_p2_customized_event(
                "drive.notice.comment_add_v1",
                self._on_drive_comment_event,
            )
            .build()
        )

    async def connect(self) -> bool:
        """Connect to Feishu/Lark."""
        if not FEISHU_AVAILABLE:
            logger.error("[Feishu] lark-oapi not installed")
            return False
        if not self._app_id or not self._app_secret:
            logger.error("[Feishu] FEISHU_APP_ID or FEISHU_APP_SECRET not set")
            return False
        if self._connection_mode not in {"websocket", "webhook"}:
            logger.error(
                "[Feishu] Unsupported FEISHU_CONNECTION_MODE=%s. Supported modes: websocket, webhook.",
                self._connection_mode,
            )
            return False

        try:
            self._app_lock_identity = self._app_id
            acquired, existing = acquire_scoped_lock(
                _FEISHU_APP_LOCK_SCOPE,
                self._app_lock_identity,
                metadata={"platform": self.platform.value},
            )
            if not acquired:
                owner_pid = existing.get("pid") if isinstance(existing, dict) else None
                message = (
                    "Another local Hermes gateway is already using this Feishu app_id"
                    + (f" (PID {owner_pid})." if owner_pid else ".")
                    + " Stop the other gateway before starting a second Feishu websocket client."
                )
                logger.error("[Feishu] %s", message)
                self._set_fatal_error("feishu_app_lock", message, retryable=False)
                return False

            self._loop = asyncio.get_running_loop()
            await self._connect_with_retry()
            self._mark_connected()
            logger.info("[Feishu] Connected in %s mode (%s)", self._connection_mode, self._domain_name)
            return True
        except Exception as exc:
            await self._release_app_lock()
            message = f"Feishu startup failed: {exc}"
            self._set_fatal_error("feishu_connect_error", message, retryable=True)
            logger.error("[Feishu] Failed to connect: %s", exc, exc_info=True)
            return False

    async def disconnect(self) -> None:
        """Disconnect from Feishu/Lark."""
        self._running = False
        await self._cancel_pending_tasks(self._pending_text_batch_tasks)
        await self._cancel_pending_tasks(self._pending_media_batch_tasks)
        self._reset_batch_buffers()
        self._disable_websocket_auto_reconnect()
        await self._stop_webhook_server()

        ws_thread_loop = self._ws_thread_loop
        if ws_thread_loop is not None and not ws_thread_loop.is_closed():
            logger.debug("[Feishu] Cancelling websocket thread tasks and stopping loop")

            def cancel_all_tasks() -> None:
                tasks = [t for t in asyncio.all_tasks(ws_thread_loop) if not t.done()]
                logger.debug("[Feishu] Found %d pending tasks in websocket thread", len(tasks))
                for task in tasks:
                    task.cancel()
                ws_thread_loop.call_later(0.1, ws_thread_loop.stop)

            ws_thread_loop.call_soon_threadsafe(cancel_all_tasks)

        ws_future = self._ws_future
        if ws_future is not None:
            try:
                logger.debug("[Feishu] Waiting for websocket thread to exit (timeout=10s)")
                await asyncio.wait_for(asyncio.shield(ws_future), timeout=10.0)
                logger.debug("[Feishu] Websocket thread exited cleanly")
            except asyncio.TimeoutError:
                logger.warning("[Feishu] Websocket thread did not exit within 10s - may be stuck")
            except asyncio.CancelledError:
                logger.debug("[Feishu] Websocket thread cancelled during disconnect")
            except Exception as exc:
                logger.debug("[Feishu] Websocket thread exited with error: %s", exc, exc_info=True)

        self._ws_future = None
        self._ws_thread_loop = None
        self._loop = None
        self._event_handler = None
        self._persist_seen_message_ids()
        await self._release_app_lock()

        self._mark_disconnected()
        logger.info("[Feishu] Disconnected")

    # =========================================================================
    # Outbound — send / edit / send_image / send_voice / ...
    # =========================================================================

    async def send(
        self,
        chat_id: str,
        content: str,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        """Send a Feishu message."""
        if not self._client:
            return SendResult(success=False, error="Not connected")

        formatted = self.format_message(content)
        chunks = self.truncate_message(formatted, self.MAX_MESSAGE_LENGTH)
        last_response = None

        try:
            for chunk in chunks:
                msg_type, payload = self._build_outbound_payload(chunk)
                try:
                    response = await self._feishu_send_with_retry(
                        chat_id=chat_id,
                        msg_type=msg_type,
                        payload=payload,
                        reply_to=reply_to,
                        metadata=metadata,
                    )
                except Exception as exc:
                    if msg_type != "post" or not _POST_CONTENT_INVALID_RE.search(str(exc)):
                        raise
                    logger.warning("[Feishu] Invalid post payload rejected by API; falling back to plain text")
                    response = await self._feishu_send_with_retry(
                        chat_id=chat_id,
                        msg_type="text",
                        payload=json.dumps({"text": _strip_markdown_to_plain_text(chunk)}, ensure_ascii=False),
                        reply_to=reply_to,
                        metadata=metadata,
                    )
                if (
                    msg_type == "post"
                    and not self._response_succeeded(response)
                    and _POST_CONTENT_INVALID_RE.search(str(getattr(response, "msg", "") or ""))
                ):
                    logger.warning("[Feishu] Post payload rejected by API response; falling back to plain text")
                    response = await self._feishu_send_with_retry(
                        chat_id=chat_id,
                        msg_type="text",
                        payload=json.dumps({"text": _strip_markdown_to_plain_text(chunk)}, ensure_ascii=False),
                        reply_to=reply_to,
                        metadata=metadata,
                    )
                last_response = response

            return self._finalize_send_result(last_response, "send failed")
        except Exception as exc:
            logger.error("[Feishu] Send error: %s", exc, exc_info=True)
            return SendResult(success=False, error=str(exc))

    async def edit_message(
        self,
        chat_id: str,
        message_id: str,
        content: str,
    ) -> SendResult:
        """Edit a previously sent Feishu text/post message."""
        if not self._client:
            return SendResult(success=False, error="Not connected")

        try:
            msg_type, payload = self._build_outbound_payload(content)
            body = self._build_update_message_body(msg_type=msg_type, content=payload)
            request = self._build_update_message_request(message_id=message_id, request_body=body)
            response = await asyncio.to_thread(self._client.im.v1.message.update, request)
            result = self._finalize_send_result(response, "update failed")
            if not result.success and msg_type == "post" and _POST_CONTENT_INVALID_RE.search(result.error or ""):
                logger.warning("[Feishu] Invalid post update payload rejected by API; falling back to plain text")
                fallback_body = self._build_update_message_body(
                    msg_type="text",
                    content=json.dumps({"text": _strip_markdown_to_plain_text(content)}, ensure_ascii=False),
                )
                fallback_request = self._build_update_message_request(message_id=message_id, request_body=fallback_body)
                fallback_response = await asyncio.to_thread(self._client.im.v1.message.update, fallback_request)
                result = self._finalize_send_result(fallback_response, "update failed")
            if result.success:
                result.message_id = message_id
            return result
        except Exception as exc:
            logger.error("[Feishu] Failed to edit message %s: %s", message_id, exc, exc_info=True)
            return SendResult(success=False, error=str(exc))

    async def send_typing(self, chat_id: str, metadata=None) -> None:
        """Feishu bot API does not expose a typing indicator."""
        return None

    async def get_chat_info(self, chat_id: str) -> Dict[str, Any]:
        """Return real chat metadata from Feishu when available."""
        fallback = {
            "chat_id": chat_id,
            "name": chat_id,
            "type": "dm",
        }
        if not self._client:
            return fallback

        cached_entry = self._chat_info_cache.get(chat_id)
        if cached_entry is not None:
            info, cached_at = cached_entry
            if time.time() - cached_at < _FEISHU_CHAT_INFO_TTL_SECONDS:
                return dict(info)
            self._chat_info_cache.pop(chat_id, None)

        try:
            request = self._build_get_chat_request(chat_id)
            response = await asyncio.to_thread(self._client.im.v1.chat.get, request)
            if not response or getattr(response, "success", lambda: False)() is False:
                code = getattr(response, "code", "unknown")
                msg = getattr(response, "msg", "chat lookup failed")
                logger.warning("[Feishu] Failed to get chat info for %s: [%s] %s", chat_id, code, msg)
                return fallback

            data = getattr(response, "data", None)
            raw_chat_type = str(getattr(data, "chat_type", "") or "").strip().lower()
            info = {
                "chat_id": chat_id,
                "name": str(getattr(data, "name", None) or chat_id),
                "type": self._map_chat_type(raw_chat_type),
                "raw_type": raw_chat_type or None,
            }
            cache = self._chat_info_cache
            if len(cache) >= _FEISHU_CHAT_INFO_CACHE_MAX:
                # Evict oldest entry
                oldest_key = next(iter(cache))
                del cache[oldest_key]
            cache[chat_id] = (info, time.time())
            return dict(info)
        except Exception:
            logger.warning("[Feishu] Failed to get chat info for %s", chat_id, exc_info=True)
            return fallback

    def format_message(self, content: str) -> str:
        """Feishu text messages are plain text by default."""
        return content.strip()

    # =========================================================================
    # Inbound event handlers
    # =========================================================================

    def _on_message_event(self, data: Any) -> None:
        """Normalize Feishu inbound events into MessageEvent.

        Called by the lark_oapi SDK's event dispatcher on a background thread.
        If the adapter loop is not currently accepting callbacks (brief window
        during startup/restart or network-flap reconnect), the event is queued
        for replay instead of dropped.
        """
        loop = self._loop
        if not self._loop_accepts_callbacks(loop):
            start_drainer = self._enqueue_pending_inbound_event(data)
            if start_drainer:
                threading.Thread(
                    target=self._drain_pending_inbound_events,
                    name="feishu-pending-inbound-drainer",
                    daemon=True,
                ).start()
            return
        future = asyncio.run_coroutine_threadsafe(
            self._handle_message_event_data(data),
            loop,
        )
        future.add_done_callback(self._log_background_failure)

    def _enqueue_pending_inbound_event(self, data: Any) -> bool:
        """Append an event to the pending-inbound queue.

        Returns True if the caller should spawn a drainer thread (no drainer
        currently scheduled), False if a drainer is already running and will
        pick up the new event on its next pass.
        """
        with self._pending_inbound_lock:
            if len(self._pending_inbound_events) >= self._pending_inbound_max_depth:
                # Queue full — drop the oldest to make room.
                dropped = self._pending_inbound_events.pop(0)
                try:
                    event = getattr(dropped, "event", None)
                    message = getattr(event, "message", None)
                    message_id = str(getattr(message, "message_id", "") or "unknown")
                except Exception:
                    message_id = "unknown"
                logger.error(
                    "[Feishu] Pending-inbound queue full (%d); dropped oldest event %s",
                    self._pending_inbound_max_depth,
                    message_id,
                )
            self._pending_inbound_events.append(data)
            depth = len(self._pending_inbound_events)
            should_start = not self._pending_drain_scheduled
            if should_start:
                self._pending_drain_scheduled = True
        logger.warning(
            "[Feishu] Queued inbound event for replay (loop not ready, queue depth=%d)",
            depth,
        )
        return should_start

    def _drain_pending_inbound_events(self) -> None:
        """Replay queued inbound events once the adapter loop is ready.

        Runs in a dedicated daemon thread. Polls ``_running`` and
        ``_loop_accepts_callbacks`` until events can be dispatched or the
        adapter shuts down.
        """
        poll_interval = 0.25
        max_wait_seconds = 120.0  # safety cap: drop queue after 2 minutes
        waited = 0.0
        try:
            while True:
                if not getattr(self, "_running", True):
                    with self._pending_inbound_lock:
                        dropped = len(self._pending_inbound_events)
                        self._pending_inbound_events.clear()
                    if dropped:
                        logger.warning(
                            "[Feishu] Dropped %d queued inbound event(s) during shutdown",
                            dropped,
                        )
                    return
                loop = self._loop
                if self._loop_accepts_callbacks(loop):
                    with self._pending_inbound_lock:
                        batch = self._pending_inbound_events[:]
                        self._pending_inbound_events.clear()
                    if not batch:
                        with self._pending_inbound_lock:
                            if not self._pending_inbound_events:
                                return
                        continue
                    dispatched = 0
                    requeue: List[Any] = []
                    for event in batch:
                        try:
                            fut = asyncio.run_coroutine_threadsafe(
                                self._handle_message_event_data(event),
                                loop,
                            )
                            fut.add_done_callback(self._log_background_failure)
                            dispatched += 1
                        except RuntimeError:
                            requeue.append(event)
                    if requeue:
                        with self._pending_inbound_lock:
                            self._pending_inbound_events[:0] = requeue
                    if dispatched:
                        logger.info(
                            "[Feishu] Replayed %d queued inbound event(s)",
                            dispatched,
                        )
                    if not requeue:
                        with self._pending_inbound_lock:
                            if not self._pending_inbound_events:
                                return
                    continue
                if waited >= max_wait_seconds:
                    with self._pending_inbound_lock:
                        dropped = len(self._pending_inbound_events)
                        self._pending_inbound_events.clear()
                    logger.error(
                        "[Feishu] Adapter loop unavailable for %.0fs; "
                        "dropped %d queued inbound event(s)",
                        max_wait_seconds,
                        dropped,
                    )
                    return
                time.sleep(poll_interval)
                waited += poll_interval
        finally:
            with self._pending_inbound_lock:
                self._pending_drain_scheduled = False

    async def _handle_message_event_data(self, data: Any) -> None:
        """Shared inbound message handling for websocket and webhook transports."""
        event = getattr(data, "event", None)
        message = getattr(event, "message", None)
        sender = getattr(event, "sender", None)
        sender_id = getattr(sender, "sender_id", None)
        if not message or not sender_id:
            logger.debug("[Feishu] Dropping malformed inbound event: missing message or sender_id")
            return

        message_id = getattr(message, "message_id", None)
        if not message_id or self._is_duplicate(message_id):
            logger.debug("[Feishu] Dropping duplicate/missing message_id: %s", message_id)
            return
        if getattr(sender, "sender_type", "") == "bot":
            logger.debug("[Feishu] Dropping bot-originated event: %s", message_id)
            return

        chat_type = getattr(message, "chat_type", "p2p")
        chat_id = getattr(message, "chat_id", "") or ""
        if chat_type != "p2p" and not self._should_accept_group_message(message, sender_id, chat_id):
            logger.debug("[Feishu] Dropping group message that failed mention/policy gate: %s", message_id)
            return
        await self._process_inbound_message(
            data=data,
            message=message,
            sender_id=sender_id,
            chat_type=chat_type,
            message_id=message_id,
        )

    def _on_message_read_event(self, data: P2ImMessageMessageReadV1) -> None:
        """Ignore read-receipt events that Hermes does not act on."""
        event = getattr(data, "event", None)
        message = getattr(event, "message", None)
        message_id = getattr(message, "message_id", None) or ""
        logger.debug("[Feishu] Ignoring message_read event: %s", message_id)

    def _on_bot_added_to_chat(self, data: Any) -> None:
        """Handle bot being added to a group chat."""
        event = getattr(data, "event", None)
        chat_id = str(getattr(event, "chat_id", "") or "")
        logger.info("[Feishu] Bot added to chat: %s", chat_id)
        self._chat_info_cache.pop(chat_id, None)

    def _on_bot_removed_from_chat(self, data: Any) -> None:
        """Handle bot being removed from a group chat."""
        event = getattr(data, "event", None)
        chat_id = str(getattr(event, "chat_id", "") or "")
        logger.info("[Feishu] Bot removed from chat: %s", chat_id)
        self._chat_info_cache.pop(chat_id, None)

    def _on_p2p_chat_entered(self, data: Any) -> None:
        logger.debug("[Feishu] User entered P2P chat with bot")

    def _on_message_recalled(self, data: Any) -> None:
        logger.debug("[Feishu] Message recalled by user")

    def _on_drive_comment_event(self, data: Any) -> None:
        """Handle drive document comment notification (drive.notice.comment_add_v1).

        Delegates to :mod:`gateway.platforms.feishu_comment` for parsing,
        logging, and reaction.
        """
        from gateway.platforms.feishu_comment import handle_drive_comment_event

        loop = self._loop
        if not self._loop_accepts_callbacks(loop):
            logger.warning("[Feishu] Dropping drive comment event before adapter loop is ready")
            return
        future = asyncio.run_coroutine_threadsafe(
            handle_drive_comment_event(self._client, data, self_open_id=self._bot_open_id),
            loop,
        )
        future.add_done_callback(self._log_background_failure)

    def _on_reaction_event(self, event_type: str, data: Any) -> None:
        """Route user reactions on bot messages as synthetic text events."""
        event = getattr(data, "event", None)
        message_id = str(getattr(event, "message_id", "") or "")
        operator_type = str(getattr(event, "operator_type", "") or "")
        reaction_type_obj = getattr(event, "reaction_type", None)
        emoji_type = str(getattr(reaction_type_obj, "emoji_type", "") or "")
        action = "added" if "created" in event_type else "removed"
        logger.debug(
            "[Feishu] Reaction %s on message %s (operator_type=%s, emoji=%s)",
            action,
            message_id,
            operator_type,
            emoji_type,
        )
        # Only process reactions from real users. Ignore app/bot-generated reactions
        # and Hermes' own ACK emoji to avoid feedback loops.
        loop = self._loop
        if (
            operator_type in {"bot", "app"}
            or emoji_type == _FEISHU_ACK_EMOJI
            or not message_id
            or loop is None
            or bool(getattr(loop, "is_closed", lambda: False)())
        ):
            return
        future = asyncio.run_coroutine_threadsafe(
            self._handle_reaction_event(event_type, data),
            loop,
        )
        future.add_done_callback(self._log_background_failure)

    # =========================================================================
    # Per-chat serialization and typing indicator
    # =========================================================================

    def _get_chat_lock(self, chat_id: str) -> asyncio.Lock:
        """Return (creating if needed) the per-chat asyncio.Lock for serial message processing."""
        lock = self._chat_locks.get(chat_id)
        if lock is None:
            lock = asyncio.Lock()
            self._chat_locks[chat_id] = lock
        return lock

    async def _handle_message_with_guards(self, event: MessageEvent) -> None:
        """Dispatch a single event through the agent pipeline with per-chat serialization
        and a persistent ACK emoji reaction before processing starts.
        """
        chat_id = getattr(event.source, "chat_id", "") or "" if event.source else ""
        chat_lock = self._get_chat_lock(chat_id)
        async with chat_lock:
            message_id = event.message_id
            if message_id:
                await self._add_ack_reaction(message_id)
            await self.handle_message(event)

    async def _add_ack_reaction(self, message_id: str) -> Optional[str]:
        """Add a persistent ACK emoji reaction to signal the message was received."""
        if not self._client or not message_id:
            return None
        try:
            from lark_oapi.api.im.v1 import (  # lazy import — keeps optional dep optional
                CreateMessageReactionRequest,
                CreateMessageReactionRequestBody,
            )
            body = (
                CreateMessageReactionRequestBody.builder()
                .reaction_type({"emoji_type": _FEISHU_ACK_EMOJI})
                .build()
            )
            request = (
                CreateMessageReactionRequest.builder()
                .message_id(message_id)
                .request_body(body)
                .build()
            )
            response = await asyncio.to_thread(self._client.im.v1.message_reaction.create, request)
            if response and getattr(response, "success", lambda: False)():
                data = getattr(response, "data", None)
                return getattr(data, "reaction_id", None)
            logger.warning(
                "[Feishu] Failed to add ack reaction to %s: code=%s msg=%s",
                message_id,
                getattr(response, "code", None),
                getattr(response, "msg", None),
            )
        except Exception:
            logger.warning("[Feishu] Failed to add ack reaction to %s", message_id, exc_info=True)
        return None

    # =========================================================================
    # Inbound processing pipeline
    # =========================================================================

    async def _process_inbound_message(
        self,
        *,
        data: Any,
        message: Any,
        sender_id: Any,
        chat_type: str,
        message_id: str,
    ) -> None:
        text, inbound_type, media_urls, media_types = await self._extract_message_content(message)
        if inbound_type == MessageType.TEXT and not text and not media_urls:
            logger.debug("[Feishu] Ignoring unsupported or empty message type: %s", getattr(message, "message_type", ""))
            return

        if inbound_type == MessageType.TEXT and text.startswith("/"):
            inbound_type = MessageType.COMMAND

        reply_to_message_id = (
            getattr(message, "parent_id", None)
            or getattr(message, "upper_message_id", None)
            or None
        )
        reply_to_text = await self._fetch_message_text(reply_to_message_id) if reply_to_message_id else None

        logger.info(
            "[Feishu] Inbound %s message received: id=%s type=%s chat_id=%s text=%r media=%d",
            "dm" if chat_type == "p2p" else "group",
            message_id,
            inbound_type.value,
            getattr(message, "chat_id", "") or "",
            text[:120],
            len(media_urls),
        )

        chat_id = getattr(message, "chat_id", "") or ""
        chat_info = await self.get_chat_info(chat_id)
        sender_profile = await self._resolve_sender_profile(sender_id)
        source = self.build_source(
            chat_id=chat_id,
            chat_name=chat_info.get("name") or chat_id or "Feishu Chat",
            chat_type=self._resolve_source_chat_type(chat_info=chat_info, event_chat_type=chat_type),
            user_id=sender_profile["user_id"],
            user_name=sender_profile["user_name"],
            thread_id=getattr(message, "thread_id", None) or None,
            user_id_alt=sender_profile["user_id_alt"],
        )
        normalized = MessageEvent(
            text=text,
            message_type=inbound_type,
            source=source,
            raw_message=data,
            message_id=message_id,
            media_urls=media_urls,
            media_types=media_types,
            reply_to_message_id=reply_to_message_id,
            reply_to_text=reply_to_text,
            timestamp=datetime.now(),
        )
        await self._dispatch_inbound_event(normalized)

    async def _dispatch_inbound_event(self, event: MessageEvent) -> None:
        """Apply Feishu-specific burst protection before entering the base adapter."""
        if event.message_type == MessageType.TEXT and not event.is_command():
            await self._enqueue_text_event(event)
            return
        if self._should_batch_media_event(event):
            await self._enqueue_media_event(event)
            return
        await self._handle_message_with_guards(event)

    # =========================================================================
    # Reaction event handler (routes to card_handler mixin's _handle_reaction_event)
    # =========================================================================

    async def _handle_reaction_event(self, event_type: str, data: Any) -> None:
        """Fetch the reacted-to message; if it was sent by this bot, emit a synthetic text event."""
        if not self._client:
            return
        event = getattr(data, "event", None)
        message_id = str(getattr(event, "message_id", "") or "")
        if not message_id:
            return

        try:
            request = self._build_get_message_request(message_id)
            response = await asyncio.to_thread(self._client.im.v1.message.get, request)
            if not response or not getattr(response, "success", lambda: False)():
                return
            items = getattr(getattr(response, "data", None), "items", None) or []
            msg = items[0] if items else None
            if not msg:
                return
            sender = getattr(msg, "sender", None)
            sender_type = str(getattr(sender, "sender_type", "") or "").lower()
            if sender_type != "app":
                return  # only route reactions on our own bot messages
            chat_id = str(getattr(msg, "chat_id", "") or "")
            chat_type_raw = str(getattr(msg, "chat_type", "p2p") or "p2p")
            if not chat_id:
                return
        except Exception:
            logger.debug("[Feishu] Failed to fetch message for reaction routing", exc_info=True)
            return

        user_id_obj = getattr(event, "user_id", None)
        reaction_type_obj = getattr(event, "reaction_type", None)
        emoji_type = str(getattr(reaction_type_obj, "emoji_type", "") or "UNKNOWN")
        action = "added" if "created" in event_type else "removed"
        synthetic_text = f"reaction:{action}:{emoji_type}"

        sender_profile = await self._resolve_sender_profile(user_id_obj)
        chat_info = await self.get_chat_info(chat_id)
        source = self.build_source(
            chat_id=chat_id,
            chat_name=chat_info.get("name") or chat_id or "Feishu Chat",
            chat_type=self._resolve_source_chat_type(chat_info=chat_info, event_chat_type=chat_type_raw),
            user_id=sender_profile["user_id"],
            user_name=sender_profile["user_name"],
            thread_id=None,
            user_id_alt=sender_profile["user_id_alt"],
        )
        synthetic_event = MessageEvent(
            text=synthetic_text,
            message_type=MessageType.TEXT,
            source=source,
            raw_message=data,
            message_id=message_id,
            timestamp=datetime.now(),
        )
        logger.info("[Feishu] Routing reaction %s:%s on bot message %s as synthetic event", action, emoji_type, message_id)
        await self._handle_message_with_guards(synthetic_event)

    # =========================================================================
    # Chat type / sender / message text helpers
    # =========================================================================

    @staticmethod
    def _map_chat_type(raw_chat_type: str) -> str:
        normalized = (raw_chat_type or "").strip().lower()
        if normalized == "p2p":
            return "dm"
        if "topic" in normalized or "thread" in normalized or "forum" in normalized:
            return "forum"
        if normalized == "group":
            return "group"
        return "dm"

    @staticmethod
    def _resolve_source_chat_type(*, chat_info: Dict[str, Any], event_chat_type: str) -> str:
        resolved = str(chat_info.get("type") or "").strip().lower()
        if resolved in {"group", "forum"}:
            return resolved
        if event_chat_type == "p2p":
            return "dm"
        return "group"

    async def _resolve_sender_profile(self, sender_id: Any) -> Dict[str, Optional[str]]:
        open_id = getattr(sender_id, "open_id", None) or None
        user_id = getattr(sender_id, "user_id", None) or None
        union_id = getattr(sender_id, "union_id", None) or None
        primary_id = open_id or user_id
        display_name = await self._resolve_sender_name_from_api(primary_id or union_id)
        return {
            "user_id": primary_id,
            "user_name": display_name,
            "user_id_alt": union_id,
        }

    def _get_cached_sender_name(self, sender_id: Optional[str]) -> Optional[str]:
        """Return a cached sender name only while its TTL is still valid."""
        if not sender_id:
            return None
        cached = self._sender_name_cache.get(sender_id)
        if cached is None:
            return None
        name, expire_at = cached
        if time.time() < expire_at:
            return name
        self._sender_name_cache.pop(sender_id, None)
        return None

    async def _resolve_sender_name_from_api(self, sender_id: Optional[str]) -> Optional[str]:
        """Fetch the sender's display name from the Feishu contact API with a 10-minute cache."""
        if not sender_id or not self._client:
            return None
        trimmed = sender_id.strip()
        if not trimmed:
            return None
        now = time.time()
        cached_name = self._get_cached_sender_name(trimmed)
        if cached_name is not None:
            return cached_name
        try:
            from lark_oapi.api.contact.v3 import GetUserRequest  # lazy import
            if trimmed.startswith("ou_"):
                id_type = "open_id"
            elif trimmed.startswith("on_"):
                id_type = "union_id"
            else:
                id_type = "user_id"
            request = GetUserRequest.builder().user_id(trimmed).user_id_type(id_type).build()
            response = await asyncio.to_thread(self._client.contact.v3.user.get, request)
            if not response or not response.success():
                return None
            user = getattr(getattr(response, "data", None), "user", None)
            name = (
                getattr(user, "name", None)
                or getattr(user, "display_name", None)
                or getattr(user, "nickname", None)
                or getattr(user, "en_name", None)
            )
            if name and isinstance(name, str):
                name = name.strip()
                if name:
                    cache = self._sender_name_cache
                    if len(cache) >= _FEISHU_SENDER_NAME_CACHE_MAX:
                        # Evict expired entries first, then oldest
                        expired = [k for k, (_, exp) in cache.items() if now >= exp]
                        for k in expired[:10]:
                            cache.pop(k, None)
                        if len(cache) >= _FEISHU_SENDER_NAME_CACHE_MAX:
                            oldest = next(iter(cache))
                            del cache[oldest]
                    cache[trimmed] = (name, now + _FEISHU_SENDER_NAME_TTL_SECONDS)
                    return name
        except Exception:
            logger.debug("[Feishu] Failed to resolve sender name for %s", sender_id, exc_info=True)
        return None

    async def _fetch_message_text(self, message_id: str) -> Optional[str]:
        if not self._client or not message_id:
            return None
        if message_id in self._message_text_cache:
            return self._message_text_cache[message_id]
        try:
            request = self._build_get_message_request(message_id)
            response = await asyncio.to_thread(self._client.im.v1.message.get, request)
            if not response or getattr(response, "success", lambda: False)() is False:
                code = getattr(response, "code", "unknown")
                msg = getattr(response, "msg", "message lookup failed")
                logger.warning("[Feishu] Failed to fetch parent message %s: [%s] %s", message_id, code, msg)
                return None
            items = getattr(getattr(response, "data", None), "items", None) or []
            parent = items[0] if items else None
            body = getattr(parent, "body", None)
            msg_type = getattr(parent, "msg_type", "") or ""
            raw_content = getattr(body, "content", "") or ""
            text = self._extract_text_from_raw_content(msg_type=msg_type, raw_content=raw_content)
            cache = self._message_text_cache
            if len(cache) >= _FEISHU_MESSAGE_TEXT_CACHE_MAX:
                oldest = next(iter(cache))
                del cache[oldest]
            cache[message_id] = text
            return text
        except Exception:
            logger.warning("[Feishu] Failed to fetch parent message %s", message_id, exc_info=True)
            return None

    def _extract_text_from_raw_content(self, *, msg_type: str, raw_content: str) -> Optional[str]:
        normalized = normalize_feishu_message(message_type=msg_type, raw_content=raw_content)
        if normalized.text_content:
            return normalized.text_content
        placeholder = normalized.metadata.get("placeholder_text") if isinstance(normalized.metadata, dict) else None
        return str(placeholder).strip() or None

    @staticmethod
    def _log_background_failure(future: Any) -> None:
        try:
            future.result()
        except Exception:
            logger.exception("[Feishu] Background inbound processing failed")

    # =========================================================================
    # Group policy and mention gating
    # =========================================================================

    def _allow_group_message(self, sender_id: Any, chat_id: str = "") -> bool:
        """Per-group policy gate for non-DM traffic."""
        sender_open_id = getattr(sender_id, "open_id", None)
        sender_user_id = getattr(sender_id, "user_id", None)
        sender_ids = {sender_open_id, sender_user_id} - {None}

        if sender_ids and self._admins and (sender_ids & self._admins):
            return True

        rule = self._group_rules.get(chat_id) if chat_id else None
        if rule:
            policy = rule.policy
            allowlist = rule.allowlist
            blacklist = rule.blacklist
        else:
            policy = self._default_group_policy or self._group_policy
            allowlist = self._allowed_group_users
            blacklist = set()

        if policy == "disabled":
            return False
        if policy == "open":
            return True
        if policy == "admin_only":
            return False
        if policy == "allowlist":
            return bool(sender_ids and (sender_ids & allowlist))
        if policy == "blacklist":
            return bool(sender_ids and not (sender_ids & blacklist))

        return bool(sender_ids and (sender_ids & self._allowed_group_users))

    def _should_accept_group_message(self, message: Any, sender_id: Any, chat_id: str = "") -> bool:
        """Require an explicit @mention before group messages enter the agent."""
        if not self._allow_group_message(sender_id, chat_id):
            return False
        # @_all is Feishu's @everyone placeholder — always route to the bot.
        raw_content = getattr(message, "content", "") or ""
        if "@_all" in raw_content:
            return True
        mentions = getattr(message, "mentions", None) or []
        if mentions:
            return self._message_mentions_bot(mentions)
        normalized = normalize_feishu_message(
            message_type=getattr(message, "message_type", "") or "",
            raw_content=raw_content,
        )
        if normalized.mentioned_ids:
            return self._post_mentions_bot(normalized.mentioned_ids)
        return False

    def _message_mentions_bot(self, mentions: List[Any]) -> bool:
        """Check whether any mention targets the configured or inferred bot identity."""
        for mention in mentions:
            mention_id = getattr(mention, "id", None)
            mention_open_id = getattr(mention_id, "open_id", None)
            mention_user_id = getattr(mention_id, "user_id", None)
            mention_name = (getattr(mention, "name", None) or "").strip()

            if self._bot_open_id and mention_open_id == self._bot_open_id:
                return True
            if self._bot_user_id and mention_user_id == self._bot_user_id:
                return True
            if self._bot_name and mention_name == self._bot_name:
                return True

        return False

    def _post_mentions_bot(self, mentioned_ids: List[str]) -> bool:
        if not mentioned_ids:
            return False
        if self._bot_open_id and self._bot_open_id in mentioned_ids:
            return True
        if self._bot_user_id and self._bot_user_id in mentioned_ids:
            return True
        return False

    # =========================================================================
    # Deduplication — seen message ID cache (persistent)
    # =========================================================================

    async def _hydrate_bot_identity(self) -> None:
        """Best-effort discovery of bot identity for precise group mention gating."""
        if not self._client:
            return
        if any((self._bot_open_id, self._bot_user_id, self._bot_name)):
            return
        try:
            request = self._build_get_application_request(app_id=self._app_id, lang="en_us")
            response = await asyncio.to_thread(self._client.application.v6.application.get, request)
            if not response or not response.success():
                code = getattr(response, "code", None)
                if code == 99991672:
                    logger.warning(
                        "[Feishu] Unable to hydrate bot identity from application info. "
                        "Grant admin:app.info:readonly or application:application:self_manage "
                        "so group @mention gating can resolve the bot name precisely."
                    )
                return
            app = getattr(getattr(response, "data", None), "app", None)
            app_name = (getattr(app, "app_name", None) or "").strip()
            if app_name:
                self._bot_name = app_name
        except Exception:
            logger.debug("[Feishu] Failed to hydrate bot identity", exc_info=True)

    def _load_seen_message_ids(self) -> None:
        try:
            payload = json.loads(self._dedup_state_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, json.JSONDecodeError):
            logger.warning("[Feishu] Failed to load persisted dedup state from %s", self._dedup_state_path, exc_info=True)
            return
        seen_data = payload.get("message_ids", {}) if isinstance(payload, dict) else {}
        now = time.time()
        ttl = _FEISHU_DEDUP_TTL_SECONDS
        # Backward-compat: old format stored a plain list of IDs (no timestamps).
        if isinstance(seen_data, list):
            entries: Dict[str, float] = {str(item).strip(): 0.0 for item in seen_data if str(item).strip()}
        elif isinstance(seen_data, dict):
            entries = {k: float(v) for k, v in seen_data.items() if isinstance(k, str) and k.strip()}
        else:
            return
        # Filter out TTL-expired entries
        valid: Dict[str, float] = {
            msg_id: ts for msg_id, ts in entries.items()
            if ts == 0.0 or ttl <= 0 or now - ts < ttl
        }
        sorted_ids = sorted(valid, key=lambda k: valid[k], reverse=True)[:self._dedup_cache_size]
        self._seen_message_order = list(reversed(sorted_ids))
        self._seen_message_ids = {k: valid[k] for k in sorted_ids}

    def _persist_seen_message_ids(self) -> None:
        try:
            self._dedup_state_path.parent.mkdir(parents=True, exist_ok=True)
            recent = self._seen_message_order[-self._dedup_cache_size:]
            payload = {"message_ids": {k: self._seen_message_ids[k] for k in recent if k in self._seen_message_ids}}
            self._dedup_state_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except OSError:
            logger.warning("[Feishu] Failed to persist dedup state to %s", self._dedup_state_path, exc_info=True)

    def _is_duplicate(self, message_id: str) -> bool:
        now = time.time()
        ttl = _FEISHU_DEDUP_TTL_SECONDS
        with self._dedup_lock:
            seen_at = self._seen_message_ids.get(message_id)
            if seen_at is not None and (ttl <= 0 or now - seen_at < ttl):
                return True
            self._seen_message_ids[message_id] = now
            self._seen_message_order.append(message_id)
            while len(self._seen_message_order) > self._dedup_cache_size:
                stale = self._seen_message_order.pop(0)
                self._seen_message_ids.pop(stale, None)
            self._dedup_dirty = True
        self._schedule_dedup_persist()
        return False

    def _schedule_dedup_persist(self) -> None:
        """Schedule a delayed dedup state persist (30s debounce)."""
        if self._dedup_persist_scheduled or not self._dedup_dirty:
            return
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        self._dedup_persist_scheduled = True
        loop.call_later(30, self._do_delayed_dedup_persist)

    def _do_delayed_dedup_persist(self) -> None:
        self._dedup_persist_scheduled = False
        if not self._dedup_dirty:
            return
        with self._dedup_lock:
            if not self._dedup_dirty:
                return
            self._dedup_dirty = False
        self._persist_seen_message_ids()

    # =========================================================================
    # Outbound payload construction and send pipeline
    # =========================================================================

    def _build_outbound_payload(self, content: str) -> tuple[str, str]:
        if _MARKDOWN_HINT_RE.search(content):
            return "post", _build_markdown_post_payload(content)
        text_payload = {"text": content}
        return "text", json.dumps(text_payload, ensure_ascii=False)

    @staticmethod
    def _response_succeeded(response: Any) -> bool:
        return bool(response and getattr(response, "success", lambda: False)())

    @staticmethod
    def _extract_response_field(response: Any, field_name: str) -> Any:
        if not FeishuAdapter._response_succeeded(response):
            return None
        data = getattr(response, "data", None)
        return getattr(data, field_name, None) if data else None

    def _response_error_result(
        self,
        response: Any,
        *,
        default_message: str,
        override_error: Optional[str] = None,
    ) -> SendResult:
        if override_error:
            return SendResult(success=False, error=override_error, raw_response=response)
        code = getattr(response, "code", "unknown")
        msg = getattr(response, "msg", default_message)
        return SendResult(success=False, error=f"[{code}] {msg}", raw_response=response)

    def _finalize_send_result(self, response: Any, default_message: str) -> SendResult:
        if not self._response_succeeded(response):
            return self._response_error_result(response, default_message=default_message)
        return SendResult(
            success=True,
            message_id=self._extract_response_field(response, "message_id"),
            raw_response=response,
        )

    async def _feishu_send_with_retry(
        self,
        *,
        chat_id: str,
        msg_type: str,
        payload: str,
        reply_to: Optional[str],
        metadata: Optional[Dict[str, Any]],
    ) -> Any:
        last_error: Optional[Exception] = None
        active_reply_to = reply_to
        for attempt in range(_FEISHU_SEND_ATTEMPTS):
            try:
                response = await self._send_raw_message(
                    chat_id=chat_id,
                    msg_type=msg_type,
                    payload=payload,
                    reply_to=active_reply_to,
                    metadata=metadata,
                )
                # If replying to a message failed because it was withdrawn or not found,
                # fall back to posting a new message directly to the chat.
                if active_reply_to and not self._response_succeeded(response):
                    code = getattr(response, "code", None)
                    if code in _FEISHU_REPLY_FALLBACK_CODES:
                        logger.warning(
                            "[Feishu] Reply to %s failed (code %s — message withdrawn/missing); "
                            "falling back to new message in chat %s",
                            active_reply_to,
                            code,
                            chat_id,
                        )
                        active_reply_to = None
                        response = await self._send_raw_message(
                            chat_id=chat_id,
                            msg_type=msg_type,
                            payload=payload,
                            reply_to=None,
                            metadata=metadata,
                        )
                return response
            except Exception as exc:
                last_error = exc
                if msg_type == "post" and _POST_CONTENT_INVALID_RE.search(str(exc)):
                    raise
                if attempt >= _FEISHU_SEND_ATTEMPTS - 1:
                    raise
                wait_seconds = 2 ** attempt
                logger.warning(
                    "[Feishu] Send attempt %d/%d failed for chat %s; retrying in %ds: %s",
                    attempt + 1,
                    _FEISHU_SEND_ATTEMPTS,
                    chat_id,
                    wait_seconds,
                    exc,
                )
                await asyncio.sleep(wait_seconds)
        raise last_error or RuntimeError("Feishu send failed")

    async def _release_app_lock(self) -> None:
        if not self._app_lock_identity:
            return
        try:
            release_scoped_lock(_FEISHU_APP_LOCK_SCOPE, self._app_lock_identity)
        except Exception as exc:
            logger.warning("[Feishu] Failed to release app lock: %s", exc, exc_info=True)
        finally:
            self._app_lock_identity = None

    # =========================================================================
    # Lark API request builders — see request_builders.py for the full set.
    # Only non-builder helpers remain here.
    # =========================================================================

    def _build_post_payload(self, content: str) -> str:
        return _build_markdown_post_payload(content)

    def _build_media_post_payload(self, *, caption: str, media_tag: Dict[str, str]) -> str:
        payload = json.loads(self._build_post_payload(caption))
        content = payload.setdefault("zh_cn", {}).setdefault("content", [])
        content.append([media_tag])
        return json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def _default_image_media_type(ext: str) -> str:
        normalized_ext = (ext or "").lower()
        if normalized_ext in {".jpg", ".jpeg"}:
            return "image/jpeg"
        return f"image/{normalized_ext.lstrip('.') or 'jpeg'}"
