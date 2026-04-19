"""Webhook Mixin for the Feishu platform adapter.

Handles webhook request processing, signature verification, rate limiting,
anomaly tracking, and server lifecycle — extracted from
``gateway.platforms.feishu`` during modular refactoring.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
from types import SimpleNamespace
from typing import Any, Dict, Optional

from gateway.platforms.feishu.constants import (
    _FEISHU_WEBHOOK_ANOMALY_THRESHOLD,
    _FEISHU_WEBHOOK_ANOMALY_TTL_SECONDS,
    _FEISHU_WEBHOOK_BODY_TIMEOUT_SECONDS,
    _FEISHU_WEBHOOK_MAX_BODY_BYTES,
    _FEISHU_WEBHOOK_RATE_LIMIT_MAX,
    _FEISHU_WEBHOOK_RATE_MAX_KEYS,
    _FEISHU_WEBHOOK_RATE_WINDOW_SECONDS,
    _FEISHU_WEBHOOK_ANOMALY_MAX_KEYS,
)

logger = logging.getLogger(__name__)

try:
    import aiohttp
    from aiohttp import web
except ImportError:
    aiohttp = None  # type: ignore[assignment]
    web = None  # type: ignore[assignment]


class FeishuWebhookMixin:
    """Mixin providing webhook handling logic for FeishuAdapter.

    Instance attributes expected on the host class:
        _webhook_runner: Optional[Any]
        _webhook_site: Optional[Any]
        _webhook_rate_counts: Dict[str, tuple[int, float]]
        _webhook_anomaly_counts: Dict[str, tuple[int, str, float]]
        _app_id: str
        _webhook_path: str
        _encrypt_key: str
        _verification_token: str

    Methods resolved at runtime on the host class:
        _on_message_event, _on_message_read_event,
        _on_bot_added_to_chat, _on_bot_removed_from_chat,
        _on_reaction_event, _on_card_action_trigger,
        _namespace_from_mapping
    """

    # ---- anomaly tracking --------------------------------------------------

    def _record_webhook_anomaly(self, remote_ip: str, status: str) -> None:
        """Increment the anomaly counter for remote_ip and emit a WARNING every threshold hits.

        Mirrors openclaw's createWebhookAnomalyTracker: TTL 6 hours, log every 25 consecutive
        error responses from the same IP.
        """
        now = time.time()
        entry = self._webhook_anomaly_counts.get(remote_ip)
        if entry is not None:
            count, _last_status, first_seen = entry
            if now - first_seen < _FEISHU_WEBHOOK_ANOMALY_TTL_SECONDS:
                count += 1
                if count % _FEISHU_WEBHOOK_ANOMALY_THRESHOLD == 0:
                    logger.warning(
                        "[Feishu] Webhook anomaly: %d consecutive error responses (%s) from %s "
                        "over the last %.0fs",
                        count,
                        status,
                        remote_ip,
                        now - first_seen,
                    )
                self._webhook_anomaly_counts[remote_ip] = (count, status, first_seen)
                return
        # Either first occurrence or TTL expired — start fresh.
        counts = self._webhook_anomaly_counts
        if len(counts) >= _FEISHU_WEBHOOK_ANOMALY_MAX_KEYS:
            # Prune expired entries first
            stale = [k for k, (_, _, fs) in counts.items() if now - fs >= _FEISHU_WEBHOOK_ANOMALY_TTL_SECONDS]
            for k in stale:
                del counts[k]
            if len(counts) >= _FEISHU_WEBHOOK_ANOMALY_MAX_KEYS:
                oldest = next(iter(counts))
                del counts[oldest]
        counts[remote_ip] = (1, status, now)

    def _clear_webhook_anomaly(self, remote_ip: str) -> None:
        """Reset the anomaly counter for remote_ip after a successful request."""
        self._webhook_anomaly_counts.pop(remote_ip, None)

    # ---- webhook server lifecycle ------------------------------------------

    async def _stop_webhook_server(self) -> None:
        if self._webhook_runner is None:
            return
        try:
            await self._webhook_runner.cleanup()
        finally:
            self._webhook_runner = None
            self._webhook_site = None

    # ---- webhook request handling ------------------------------------------

    async def _handle_webhook_request(self, request: Any) -> Any:
        remote_ip = (getattr(request, "remote", None) or "unknown")

        # Rate limiting — composite key: app_id:path:remote_ip (matches openclaw key structure).
        rate_key = f"{self._app_id}:{self._webhook_path}:{remote_ip}"
        if not self._check_webhook_rate_limit(rate_key):
            logger.warning("[Feishu] Webhook rate limit exceeded for %s", remote_ip)
            self._record_webhook_anomaly(remote_ip, "429")
            return web.Response(status=429, text="Too Many Requests")

        # Content-Type guard — Feishu always sends application/json.
        headers = getattr(request, "headers", {}) or {}
        content_type = str(headers.get("Content-Type", "") or "").split(";")[0].strip().lower()
        if content_type and content_type != "application/json":
            logger.warning("[Feishu] Webhook rejected: unexpected Content-Type %r from %s", content_type, remote_ip)
            self._record_webhook_anomaly(remote_ip, "415")
            return web.Response(status=415, text="Unsupported Media Type")

        # Body size guard — reject early via Content-Length when present.
        content_length = getattr(request, "content_length", None)
        if content_length is not None and content_length > _FEISHU_WEBHOOK_MAX_BODY_BYTES:
            logger.warning("[Feishu] Webhook body too large (%d bytes) from %s", content_length, remote_ip)
            self._record_webhook_anomaly(remote_ip, "413")
            return web.Response(status=413, text="Request body too large")

        try:
            body_bytes: bytes = await asyncio.wait_for(
                request.read(),
                timeout=_FEISHU_WEBHOOK_BODY_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.warning("[Feishu] Webhook body read timed out after %ds from %s", _FEISHU_WEBHOOK_BODY_TIMEOUT_SECONDS, remote_ip)
            self._record_webhook_anomaly(remote_ip, "408")
            return web.Response(status=408, text="Request Timeout")
        except Exception:
            self._record_webhook_anomaly(remote_ip, "400")
            return web.json_response({"code": 400, "msg": "failed to read body"}, status=400)

        if len(body_bytes) > _FEISHU_WEBHOOK_MAX_BODY_BYTES:
            logger.warning("[Feishu] Webhook body exceeds limit (%d bytes) from %s", len(body_bytes), remote_ip)
            self._record_webhook_anomaly(remote_ip, "413")
            return web.Response(status=413, text="Request body too large")

        try:
            payload = json.loads(body_bytes.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._record_webhook_anomaly(remote_ip, "400")
            return web.json_response({"code": 400, "msg": "invalid json"}, status=400)

        # URL verification challenge — respond before other checks so that Feishu's
        # subscription setup works even before encrypt_key is wired.
        if payload.get("type") == "url_verification":
            return web.json_response({"challenge": payload.get("challenge", "")})

        # Verification token check — second layer of defence beyond signature (matches openclaw).
        if self._verification_token:
            header = payload.get("header") or {}
            incoming_token = str(header.get("token") or payload.get("token") or "")
            if not incoming_token or not hmac.compare_digest(incoming_token, self._verification_token):
                logger.warning("[Feishu] Webhook rejected: invalid verification token from %s", remote_ip)
                self._record_webhook_anomaly(remote_ip, "401-token")
                return web.Response(status=401, text="Invalid verification token")

        # Timing-safe signature verification (only enforced when encrypt_key is set).
        if self._encrypt_key and not self._is_webhook_signature_valid(request.headers, body_bytes):
            logger.warning("[Feishu] Webhook rejected: invalid signature from %s", remote_ip)
            self._record_webhook_anomaly(remote_ip, "401-sig")
            return web.Response(status=401, text="Invalid signature")

        if payload.get("encrypt"):
            logger.error("[Feishu] Encrypted webhook payloads are not supported by Hermes webhook mode")
            self._record_webhook_anomaly(remote_ip, "400-encrypted")
            return web.json_response({"code": 400, "msg": "encrypted webhook payloads are not supported"}, status=400)

        self._clear_webhook_anomaly(remote_ip)

        event_type = str((payload.get("header") or {}).get("event_type") or "")
        data = self._namespace_from_mapping(payload)
        if event_type == "im.message.receive_v1":
            self._on_message_event(data)
        elif event_type == "im.message.message_read_v1":
            self._on_message_read_event(data)
        elif event_type == "im.chat.member.bot.added_v1":
            self._on_bot_added_to_chat(data)
        elif event_type == "im.chat.member.bot.deleted_v1":
            self._on_bot_removed_from_chat(data)
        elif event_type in ("im.message.reaction.created_v1", "im.message.reaction.deleted_v1"):
            self._on_reaction_event(event_type, data)
        elif event_type == "card.action.trigger":
            self._on_card_action_trigger(data)
        else:
            logger.debug("[Feishu] Ignoring webhook event type: %s", event_type or "unknown")
        return web.json_response({"code": 0, "msg": "ok"})

    # ---- signature / rate-limit helpers ------------------------------------

    def _is_webhook_signature_valid(self, headers: Any, body_bytes: bytes) -> bool:
        """Verify Feishu webhook signature using timing-safe comparison.

        Feishu signature algorithm:
            SHA256(timestamp + nonce + encrypt_key + body_string)
        Headers checked: x-lark-request-timestamp, x-lark-request-nonce, x-lark-signature.
        """
        timestamp = str(headers.get("x-lark-request-timestamp", "") or "")
        nonce = str(headers.get("x-lark-request-nonce", "") or "")
        signature = str(headers.get("x-lark-signature", "") or "")
        if not timestamp or not nonce or not signature:
            return False
        try:
            body_str = body_bytes.decode("utf-8", errors="replace")
            content = f"{timestamp}{nonce}{self._encrypt_key}{body_str}"
            computed = hashlib.sha256(content.encode("utf-8")).hexdigest()
            return hmac.compare_digest(computed, signature)
        except Exception:
            logger.debug("[Feishu] Signature verification raised an exception", exc_info=True)
            return False

    def _check_webhook_rate_limit(self, rate_key: str) -> bool:
        """Return False when the composite rate_key has exceeded _FEISHU_WEBHOOK_RATE_LIMIT_MAX.

        The rate_key is composed as "{app_id}:{path}:{remote_ip}" — matching openclaw's key
        structure so the limit is scoped to a specific (account, endpoint, IP) triple rather
        than a bare IP, which causes fewer false-positive denials in multi-tenant setups.

        The tracking dict is capped at _FEISHU_WEBHOOK_RATE_MAX_KEYS entries to prevent unbounded
        memory growth. Stale (expired) entries are pruned when the cap is reached.
        """
        now = time.time()
        # Fast path: existing entry within the current window.
        entry = self._webhook_rate_counts.get(rate_key)
        if entry is not None:
            count, window_start = entry
            if now - window_start < _FEISHU_WEBHOOK_RATE_WINDOW_SECONDS:
                if count >= _FEISHU_WEBHOOK_RATE_LIMIT_MAX:
                    return False
                self._webhook_rate_counts[rate_key] = (count + 1, window_start)
                return True
        # New window for an existing key, or a brand-new key — prune stale entries first.
        if len(self._webhook_rate_counts) >= _FEISHU_WEBHOOK_RATE_MAX_KEYS:
            stale_keys = [
                k for k, (_, ws) in self._webhook_rate_counts.items()
                if now - ws >= _FEISHU_WEBHOOK_RATE_WINDOW_SECONDS
            ]
            for k in stale_keys:
                del self._webhook_rate_counts[k]
            # If still at capacity after pruning, allow through without tracking.
            if rate_key not in self._webhook_rate_counts and len(self._webhook_rate_counts) >= _FEISHU_WEBHOOK_RATE_MAX_KEYS:
                return True
        self._webhook_rate_counts[rate_key] = (1, now)
        return True
