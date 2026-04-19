"""Feishu interactive card handler mixin.

Extracted from ``gateway.platforms.feishu`` during modular refactoring.
Handles approval card rendering, card-action callbacks, and approval resolution.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Dict, Optional

from .constants import (
    _APPROVAL_CHOICE_MAP,
    _APPROVAL_LABEL_MAP,
    _FEISHU_ACK_EMOJI,
    _FEISHU_CARD_ACTION_DEDUP_TTL_SECONDS,
)

try:
    from lark_oapi.event.callback.model.p2_card_action_trigger import (
        CallBackCard,
        P2CardActionTriggerResponse,
    )
except ImportError:
    CallBackCard = None  # type: ignore[assignment]
    P2CardActionTriggerResponse = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class FeishuCardHandlerMixin:
    """Mixin providing interactive card action handling for the Feishu adapter."""

    # -- send / render --------------------------------------------------------

    async def send_exec_approval(
        self, chat_id: str, command: str, session_key: str,
        description: str = "dangerous command",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Send an interactive card with approval buttons.

        The buttons carry ``hermes_action`` in their value dict so that
        ``_handle_card_action_event`` can intercept them and call
        ``resolve_gateway_approval()`` to unblock the waiting agent thread.
        """
        if not self._client:
            from gateway.platforms.base import SendResult
            return SendResult(success=False, error="Not connected")

        try:
            approval_id = next(self._approval_counter)
            cmd_preview = command[:3000] + "..." if len(command) > 3000 else command

            def _btn(label: str, action_name: str, btn_type: str = "default") -> dict:
                return {
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": label},
                    "type": btn_type,
                    "value": {"hermes_action": action_name, "approval_id": approval_id},
                }

            card = {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"content": "⚠️ Command Approval Required", "tag": "plain_text"},
                    "template": "orange",
                },
                "elements": [
                    {
                        "tag": "markdown",
                        "content": f"```\n{cmd_preview}\n```\n**Reason:** {description}",
                    },
                    {
                        "tag": "action",
                        "actions": [
                            _btn("✅ Allow Once", "approve_once", "primary"),
                            _btn("✅ Session", "approve_session"),
                            _btn("✅ Always", "approve_always"),
                            _btn("❌ Deny", "deny", "danger"),
                        ],
                    },
                ],
            }

            payload = json.dumps(card, ensure_ascii=False)
            response = await self._feishu_send_with_retry(
                chat_id=chat_id,
                msg_type="interactive",
                payload=payload,
                reply_to=None,
                metadata=metadata,
            )

            result = self._finalize_send_result(response, "send_exec_approval failed")
            if result.success:
                self._approval_state[approval_id] = {
                    "session_key": session_key,
                    "message_id": result.message_id or "",
                    "chat_id": chat_id,
                }
            return result
        except Exception as exc:
            logger.warning("[Feishu] send_exec_approval failed: %s", exc)
            from gateway.platforms.base import SendResult
            return SendResult(success=False, error=str(exc))

    @staticmethod
    def _build_resolved_approval_card(*, choice: str, user_name: str) -> Dict[str, Any]:
        """Build raw card JSON for a resolved approval action."""
        icon = "❌" if choice == "deny" else "✅"
        label = _APPROVAL_LABEL_MAP.get(choice, "Resolved")
        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"content": f"{icon} {label}", "tag": "plain_text"},
                "template": "red" if choice == "deny" else "green",
            },
            "elements": [
                {
                    "tag": "markdown",
                    "content": f"{icon} **{label}** by {user_name}",
                },
            ],
        }

    # -- card-action callback entry -------------------------------------------

    def _on_card_action_trigger(self, data: Any) -> Any:
        """Handle card-action callback from the Feishu SDK (synchronous).

        For approval actions: parses the event once, returns the resolved card
        inline (the only reliable way to sync all clients), and schedules a
        lightweight async method to actually unblock the agent.

        For other card actions: delegates to ``_handle_card_action_event``.
        """
        loop = self._loop
        if not self._loop_accepts_callbacks(loop):
            logger.warning("[Feishu] Dropping card action before adapter loop is ready")
            return P2CardActionTriggerResponse() if P2CardActionTriggerResponse else None

        event = getattr(data, "event", None)
        action = getattr(event, "action", None)
        action_value = getattr(action, "value", {}) or {}
        hermes_action = action_value.get("hermes_action") if isinstance(action_value, dict) else None

        if hermes_action:
            return self._handle_approval_card_action(event=event, action_value=action_value, loop=loop)

        # Self-evolution proposal callbacks (approve/modify/reject)
        proposal_id = action_value.get("proposal_id") if isinstance(action_value, dict) else None
        if proposal_id:
            return self._handle_evolution_card_action(event=event, action_value=action_value, loop=loop)

        # Task plan approval callbacks (approve/modify from feishu-enhanced plugin)
        task_plan_action = action_value.get("task_plan_action") if isinstance(action_value, dict) else None
        if task_plan_action:
            context = getattr(event, "context", None)
            chat_id = str(getattr(context, "open_chat_id", "") or "")
            return self._handle_task_plan_action(
                event=event, action_value=action_value, loop=loop, chat_id=chat_id,
            )

        # Task confirm callbacks (plan/execute from feishu-enhanced plugin)
        task_confirm_action = action_value.get("task_confirm_action") if isinstance(action_value, dict) else None
        if task_confirm_action:
            context = getattr(event, "context", None)
            chat_id = str(getattr(context, "open_chat_id", "") or "")
            return self._handle_task_confirm_action(
                event=event, action_value=action_value, loop=loop, chat_id=chat_id,
            )

        self._submit_on_loop(loop, self._handle_card_action_event(data))
        if P2CardActionTriggerResponse is None:
            return None
        return P2CardActionTriggerResponse()

    # -- helpers for thread-safe loop submission --------------------------------

    @staticmethod
    def _loop_accepts_callbacks(loop: Any) -> bool:
        """Return True when the adapter loop can accept thread-safe submissions."""
        return loop is not None and not bool(getattr(loop, "is_closed", lambda: False)())

    def _submit_on_loop(self, loop: Any, coro: Any) -> None:
        """Schedule background work on the adapter loop with shared failure logging."""
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        future.add_done_callback(self._log_background_failure)

    # -- approval card action --------------------------------------------------

    def _handle_approval_card_action(self, *, event: Any, action_value: Dict[str, Any], loop: Any) -> Any:
        """Schedule approval resolution and build the synchronous callback response."""
        approval_id = action_value.get("approval_id")
        if approval_id is None:
            logger.debug("[Feishu] Card action missing approval_id, ignoring")
            return P2CardActionTriggerResponse() if P2CardActionTriggerResponse else None
        choice = _APPROVAL_CHOICE_MAP.get(action_value.get("hermes_action"), "deny")

        operator = getattr(event, "operator", None)
        open_id = str(getattr(operator, "open_id", "") or "")
        user_name = self._get_cached_sender_name(open_id) or open_id

        self._submit_on_loop(loop, self._resolve_approval(approval_id, choice, user_name))

        if P2CardActionTriggerResponse is None:
            return None
        response = P2CardActionTriggerResponse()
        if CallBackCard is not None:
            card = CallBackCard()
            card.type = "raw"
            card.data = self._build_resolved_approval_card(choice=choice, user_name=user_name)
            response.card = card
        return response

    # -- evolution card action --------------------------------------------------

    def _handle_evolution_card_action(self, *, event: Any, action_value: Dict[str, Any], loop: Any) -> Any:
        """Handle self_evolution proposal card action (approve/modify/reject)."""
        action = action_value.get("action", "")
        proposal_id = action_value.get("proposal_id", "")
        if not action or not proposal_id:
            return P2CardActionTriggerResponse() if P2CardActionTriggerResponse else None

        operator = getattr(event, "operator", None)
        open_id = str(getattr(operator, "open_id", "") or "")
        user_name = self._get_cached_sender_name(open_id) or open_id

        self._submit_on_loop(loop, self._resolve_evolution_action(action, proposal_id, user_name))

        if P2CardActionTriggerResponse is None:
            return None
        response = P2CardActionTriggerResponse()
        if CallBackCard is not None:
            icon = {"approve": "✅", "modify": "✏️", "reject": "❌"}.get(action, "📋")
            label = {"approve": "已通过", "modify": "已修改", "reject": "已拒绝"}.get(action, "已处理")
            template = "red" if action == "reject" else "green" if action == "approve" else "blue"
            card = CallBackCard()
            card.type = "raw"
            card.data = {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"content": f"{icon} {label}", "tag": "plain_text"},
                    "template": template,
                },
                "elements": [
                    {"tag": "markdown", "content": f"{icon} **{label}** by {user_name}"},
                    {"tag": "note", "elements": [
                        {"tag": "plain_text", "content": f"提案 {proposal_id[:12]}…"},
                    ]},
                ],
            }
            response.card = card
        return response

    async def _resolve_evolution_action(self, action: str, proposal_id: str, user_name: str) -> None:
        """Execute the self_evolution proposal callback.

        NOTE: The current card design only has action buttons (approve/modify/reject)
        without a text input element, so ``user_input`` is always empty for modify
        actions.  A future card redesign could add an input field.
        """
        try:
            from self_evolution.feishu_notifier import FeishuNotifier
            notifier = FeishuNotifier()
            notifier.handle_callback(action, proposal_id)
            logger.info("Evolution proposal %s %s by %s", proposal_id, action, user_name)
        except Exception as exc:
            logger.error("Failed to resolve evolution proposal from Feishu button: %s", exc)

    # -- task plan card action (feishu-enhanced plugin) -----------------------

    def _handle_task_plan_action(self, *, event: Any, action_value: Dict[str, Any], loop: Any, chat_id: str) -> Any:
        """Handle plan approval card button clicks (confirm/modify).

        Buttons carry ``task_plan_action`` values set by the feishu-enhanced
        plugin's ``task_plan_card.build_plan_card()``.

        Flow:
          - approve: transition PlanState → approved, schedule ProgressCard,
            send synthetic message to trigger agent execution.
          - modify:  transition PlanState → planning (user types feedback in chat).
        """
        action = action_value.get("task_plan_action", "")

        operator = getattr(event, "operator", None)
        open_id = str(getattr(operator, "open_id", "") or "")
        user_name = self._get_cached_sender_name(open_id) or open_id

        try:
            from hermes_plugins.feishu_enhanced.session_store import store
            from hermes_plugins.feishu_enhanced.plan_state import get_state

            session = store.find_session_by_chat_id(chat_id)
            if session:
                state = get_state(session.session_id)

                if action == "approve":
                    result = state.approve()
                    if result.get("status") == "approved":
                        self._submit_on_loop(
                            loop,
                            self._create_plan_progress(session.session_id, chat_id, result),
                        )
                        self._submit_on_loop(
                            loop,
                            self._send_plan_synthetic(chat_id, open_id, "确认执行方案"),
                        )
                elif action == "modify":
                    state.modify("")
                    # No synthetic message — resolved card tells user to type feedback.
                    # Their next chat message triggers the agent in PLANNING mode.
        except Exception as exc:
            logger.warning("[Feishu] task_plan_action handler error: %s", exc)

        # Build inline resolved card (sync client update).
        resolved_card_data = None
        try:
            from hermes_plugins.feishu_enhanced.task_plan_card import build_resolved_card
            resolved_card_data = build_resolved_card(action, user_name)
        except Exception:
            resolved_card_data = {
                "config": {"wide_screen_mode": True},
                "header": {"title": {"content": "已处理", "tag": "plain_text"}, "template": "grey"},
                "elements": [],
            }

        if P2CardActionTriggerResponse is None:
            return None
        response = P2CardActionTriggerResponse()
        if CallBackCard is not None and resolved_card_data:
            card = CallBackCard()
            card.type = "raw"
            card.data = resolved_card_data
            response.card = card
        return response

    async def _create_plan_progress(self, session_id: str, chat_id: str, plan_data: dict) -> None:
        """Create and send a ProgressCard after plan approval."""
        try:
            from hermes_plugins.feishu_enhanced.session_store import store
            from gateway.feishu_progress import ProgressCard

            adapter = store.get_adapter(session_id) or self
            card = ProgressCard(
                adapter=adapter,
                chat_id=chat_id,
                metadata={"session_id": session_id},
            )
            subtasks = plan_data.get("subtasks", [])
            if subtasks and hasattr(card, "set_steps"):
                card.set_steps(subtasks)

            await card.send_initial(plan_data.get("goal", "")[:200])

            session = store.get_or_create(session_id)
            session.progress_card = card
            logger.info("[Feishu] Progress card created for session %s", session_id[:20])
        except Exception as exc:
            logger.warning("[Feishu] Failed to create progress card: %s", exc)

    async def _send_plan_synthetic(self, chat_id: str, open_id: str, text: str) -> None:
        """Send a synthetic message to trigger agent execution after plan approval."""
        try:
            sender_id = SimpleNamespace(open_id=open_id, user_id=None, union_id=None)
            sender_profile = await self._resolve_sender_profile(sender_id)
            chat_info = await self.get_chat_info(chat_id)
            source = self.build_source(
                chat_id=chat_id,
                chat_name=chat_info.get("name") or chat_id or "Feishu Chat",
                chat_type=self._resolve_source_chat_type(chat_info=chat_info, event_chat_type="group"),
                user_id=sender_profile["user_id"],
                user_name=sender_profile["user_name"],
                thread_id=None,
                user_id_alt=sender_profile["user_id_alt"],
            )
            from gateway.platforms.base import MessageEvent, MessageType
            synthetic_event = MessageEvent(
                text=text,
                message_type=MessageType.COMMAND,
                source=source,
                raw_message=None,
                message_id=str(uuid.uuid4()),
                timestamp=datetime.now(),
            )
            await self._handle_message_with_guards(synthetic_event)
        except Exception as exc:
            logger.warning("[Feishu] Plan synthetic message failed: %s", exc)

    # -- task confirm card action (feishu-enhanced plugin) --------------------

    def _handle_task_confirm_action(self, *, event: Any, action_value: Dict[str, Any], loop: Any, chat_id: str) -> Any:
        """Handle task confirmation card button clicks (plan/execute).

        Buttons carry ``task_confirm_action`` values set by the feishu-enhanced
        plugin's ``confirm_card.build_confirm_card()``.
        """
        action = action_value.get("task_confirm_action", "")

        operator = getattr(event, "operator", None)
        open_id = str(getattr(operator, "open_id", "") or "")
        user_name = self._get_cached_sender_name(open_id) or open_id

        try:
            from hermes_plugins.feishu_enhanced.session_store import store
            session = store.find_session_by_chat_id(chat_id)
            if session:
                if action == "plan":
                    session.force_plan = True
                elif action == "execute":
                    session.force_plan = False
        except Exception as exc:
            logger.warning("[Feishu] task_confirm_action handler error: %s", exc)

        # Build inline resolved card.
        resolved_card_data = None
        try:
            from hermes_plugins.feishu_enhanced.confirm_card import build_confirm_resolved_card
            resolved_card_data = build_confirm_resolved_card(action, user_name)
        except Exception:
            resolved_card_data = {
                "config": {"wide_screen_mode": True},
                "header": {"title": {"content": "已处理", "tag": "plain_text"}, "template": "grey"},
                "elements": [],
            }

        if P2CardActionTriggerResponse is None:
            return None
        response = P2CardActionTriggerResponse()
        if CallBackCard is not None and resolved_card_data:
            card = CallBackCard()
            card.type = "raw"
            card.data = resolved_card_data
            response.card = card
        return response

    # -- approval resolution -------------------------------------------------

    async def _resolve_approval(self, approval_id: Any, choice: str, user_name: str) -> None:
        """Pop approval state and unblock the waiting agent thread."""
        state = self._approval_state.pop(approval_id, None)
        if not state:
            logger.debug("[Feishu] Approval %s already resolved or unknown", approval_id)
            return
        try:
            from tools.approval import resolve_gateway_approval
            count = resolve_gateway_approval(state["session_key"], choice)
            logger.info(
                "Feishu button resolved %d approval(s) for session %s (choice=%s, user=%s)",
                count, state["session_key"], choice, user_name,
            )
        except Exception as exc:
            logger.error("Failed to resolve gateway approval from Feishu button: %s", exc)

    # -- dedup -----------------------------------------------------------------

    def _is_card_action_duplicate(self, token: str) -> bool:
        """Return True if this card action token was already processed within the dedup window."""
        now = time.time()
        ttl = _FEISHU_CARD_ACTION_DEDUP_TTL_SECONDS
        # Probabilistic cleanup: when the token set is large, sample a few
        # entries to evict expired ones rather than scanning the entire dict.
        tokens = self._card_action_tokens
        if len(tokens) > 256:
            keys = list(tokens.keys())
            for k in keys[:min(8, len(keys))]:
                if now - tokens[k] > ttl:
                    del tokens[k]
        if token in tokens:
            return True
        tokens[token] = now
        return False

    # -- generic card action event router --------------------------------------

    async def _handle_card_action_event(self, data: Any) -> None:
        """Route Feishu interactive card button clicks as synthetic COMMAND events."""
        event = getattr(data, "event", None)
        token = str(getattr(event, "token", "") or "")
        if token and self._is_card_action_duplicate(token):
            logger.debug("[Feishu] Dropping duplicate card action token: %s", token)
            return

        context = getattr(event, "context", None)
        chat_id = str(getattr(context, "open_chat_id", "") or "")
        operator = getattr(event, "operator", None)
        open_id = str(getattr(operator, "open_id", "") or "")
        if not chat_id or not open_id:
            logger.debug("[Feishu] Card action missing chat_id or operator open_id, dropping")
            return

        action = getattr(event, "action", None)
        action_tag = str(getattr(action, "tag", "") or "button")
        action_value = getattr(action, "value", {}) or {}

        synthetic_text = f"/card {action_tag}"
        if action_value:
            try:
                synthetic_text += f" {json.dumps(action_value, ensure_ascii=False)}"
            except Exception:
                pass

        sender_id = SimpleNamespace(open_id=open_id, user_id=None, union_id=None)
        sender_profile = await self._resolve_sender_profile(sender_id)
        chat_info = await self.get_chat_info(chat_id)
        source = self.build_source(
            chat_id=chat_id,
            chat_name=chat_info.get("name") or chat_id or "Feishu Chat",
            chat_type=self._resolve_source_chat_type(chat_info=chat_info, event_chat_type="group"),
            user_id=sender_profile["user_id"],
            user_name=sender_profile["user_name"],
            thread_id=None,
            user_id_alt=sender_profile["user_id_alt"],
        )
        from gateway.platforms.base import MessageEvent, MessageType
        synthetic_event = MessageEvent(
            text=synthetic_text,
            message_type=MessageType.COMMAND,
            source=source,
            raw_message=data,
            message_id=token or str(uuid.uuid4()),
            timestamp=datetime.now(),
        )
        logger.info("[Feishu] Routing card action %r from %s in %s as synthetic command", action_tag, open_id, chat_id)
        await self._handle_message_with_guards(synthetic_event)
