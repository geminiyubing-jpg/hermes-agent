"""Feishu interactive-card progress reporter for long-running tasks.

Builds and updates a Feishu interactive card that shows task steps and
overall progress.  All methods swallow exceptions so the main gateway
flow is never blocked by a card failure.

This is the canonical implementation — the feishu-enhanced plugin's
``progress_card.py`` re-exports from here.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Minimum seconds between card-update API calls (anti-flood).
_MIN_UPDATE_INTERVAL = float(os.getenv("HERMES_PROGRESS_INTERVAL", "10"))

# Status icons for step display (module-level constant to avoid per-call dict creation).
_STATUS_ICONS = {"pending": "⏳", "running": "🔄", "done": "✅", "failed": "❌"}

# Mapping from todo tool status to ProgressCard step status.
_TODO_STATUS_MAP = {
    "pending": "pending",
    "in_progress": "running",
    "completed": "done",
    "cancelled": "failed",
}

# Keywords used to detect existing quality-check steps so finalize() doesn't duplicate.
_QUALITY_STEP_KEYWORDS = frozenset({
    "质量", "验收", "检查", "quality", "verify", "check",
})


@dataclass
class StepInfo:
    name: str
    status: str = "pending"   # pending | running | done | failed
    detail: str = ""
    started_at: float = 0.0


@dataclass
class ProgressCard:
    """Manages a Feishu interactive-card lifecycle for task progress."""

    adapter: Any                      # FeishuPlatformAdapter
    chat_id: str
    metadata: Optional[Dict[str, Any]] = None

    # Internal state
    _card_msg_id: Optional[str] = field(default=None, init=False, repr=False)
    _title: str = field(default="", init=False, repr=False)
    _task_summary: str = field(default="", init=False, repr=False)
    _steps: List[StepInfo] = field(default_factory=list, init=False, repr=False)
    _last_update_ts: float = field(default=0.0, init=False, repr=False)
    _start_ts: float = field(default=0.0, init=False, repr=False)
    _finalized: bool = field(default=False, init=False, repr=False)
    _current_tool: str = field(default="", init=False, repr=False)
    _send_failed: bool = field(default=False, init=False, repr=False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def send_initial(self, task_summary: str) -> None:
        """Send the initial progress card and store the message id."""
        if self._send_failed:
            return
        try:
            self._title = "任务处理中..."
            self._task_summary = task_summary[:200]
            self._start_ts = time.time()
            card = self._build_card()
            payload = json.dumps(card, ensure_ascii=False)
            result = await self.adapter._feishu_send_with_retry(
                chat_id=self.chat_id,
                msg_type="interactive",
                payload=payload,
                reply_to=None,
                metadata=self.metadata,
            )
            resp = self.adapter._finalize_send_result(result, "progress card send failed")
            if resp.success and resp.message_id:
                self._card_msg_id = resp.message_id
                logger.info("[progress-card] Sent initial card msg_id=%s", self._card_msg_id)
            else:
                logger.debug("[progress-card] Initial send failed: %s", resp.error)
                self._send_failed = True
        except Exception as exc:
            logger.debug("[progress-card] send_initial error: %s", exc)
            self._send_failed = True

    def set_steps(self, step_names: List[str]) -> None:
        """Define the step list (called by gateway after agent analysis)."""
        self._steps = [StepInfo(name=n) for n in step_names]

    @property
    def steps(self) -> List[StepInfo]:
        """Read-only access to the step list."""
        return self._steps

    def sync_from_todos(self, todos: List[Dict[str, str]]) -> None:
        """Sync step status from todo tool results.

        Maps todo item status to ProgressCard step status:
          pending → pending, in_progress → running,
          completed → done, cancelled → failed

        Args:
            todos: list of {"id": "step_N", "content": "...", "status": "..."}
        """
        if not self._steps:
            return

        changed = False
        for todo_item in todos:
            try:
                idx = int(todo_item.get("id", "").replace("step_", "")) - 1
            except (ValueError, AttributeError):
                continue
            if 0 <= idx < len(self._steps):
                new_status = _TODO_STATUS_MAP.get(todo_item.get("status", ""), "pending")
                if self._steps[idx].status != new_status:
                    self._steps[idx].status = new_status
                    changed = True
                    if new_status == "running" and not self._steps[idx].started_at:
                        self._steps[idx].started_at = time.time()

        if changed:
            self._current_tool = "todo_sync"
            self._last_update_ts = 0  # Force update regardless of rate limit
            try:
                from hermes_plugins.feishu_enhanced.session_store import store
                loop = store.gateway_loop
                if loop and not loop.is_closed():
                    asyncio.run_coroutine_threadsafe(self._do_edit(), loop)
                else:
                    logger.debug("[progress-card] sync_from_todos: no gateway loop")
            except Exception as exc:
                logger.debug("[progress-card] sync_from_todos error: %s", exc)

    async def update_progress(self, current_tool: str = "", step_index: int = -1,
                              step_status: str = "", step_detail: str = "") -> None:
        """Push a progress update (rate-limited)."""
        if self._finalized or not self._card_msg_id:
            return
        try:
            if 0 <= step_index < len(self._steps):
                step = self._steps[step_index]
                step.status = step_status or step.status
                step.detail = step_detail or step.detail
                if step_status == "running" and not step.started_at:
                    step.started_at = time.time()

            if current_tool:
                self._current_tool = current_tool

            now = time.monotonic()
            if now - self._last_update_ts < _MIN_UPDATE_INTERVAL:
                return

            await self._do_edit()
            self._last_update_ts = now
        except Exception as exc:
            logger.debug("[progress-card] update_progress error: %s", exc)

    async def finalize(self, summary: str, success: bool = True) -> None:
        """Mark the task as complete and update the card one last time."""
        if self._finalized or not self._card_msg_id:
            return
        try:
            self._finalized = True

            elapsed = int(time.time() - self._start_ts) if self._start_ts else 0
            if success:
                self._title = f"任务完成 (耗时 {elapsed}秒)"
            else:
                self._title = f"任务失败 (耗时 {elapsed}秒)"

            # Add quality check step if not already present
            has_quality_step = any(
                any(kw in s.name.lower() for kw in _QUALITY_STEP_KEYWORDS)
                for s in self._steps
            )
            if not has_quality_step and self._steps:
                qc_step = StepInfo(name="质量验收")
                if success:
                    qc_step.status = "done"
                    qc_step.detail = "通过"
                else:
                    qc_step.status = "failed"
                self._steps.append(qc_step)

            for s in self._steps:
                if s.status in ("pending", "running"):
                    s.status = "done" if success else "failed"
            if summary:
                self._current_tool = ""

            # Force update regardless of rate limit
            self._last_update_ts = 0
            await self._do_edit(summary=summary[:300] if summary else None)
            logger.info("[progress-card] Finalized card msg_id=%s", self._card_msg_id)
        except Exception as exc:
            logger.debug("[progress-card] finalize error: %s", exc)

    @property
    def is_active(self) -> bool:
        return self._card_msg_id is not None and not self._finalized

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_card(self, summary_override: Optional[str] = None) -> Dict[str, Any]:
        elements: List[Dict[str, Any]] = []

        if self._task_summary:
            elements.append({"tag": "markdown", "content": f"**任务：** {self._task_summary}"})

        if self._start_ts:
            elapsed = int(time.time() - self._start_ts)
            mins, secs = divmod(elapsed, 60)
            if mins > 0:
                time_str = f"{mins}分{secs}秒"
            else:
                time_str = f"{secs}秒"
            elements.append({"tag": "markdown", "content": f"**已用时：** {time_str}"})

        if self._steps:
            total = len(self._steps)
            done_count = sum(1 for s in self._steps if s.status == "done")
            fail_count = sum(1 for s in self._steps if s.status == "failed")
            running_count = sum(1 for s in self._steps if s.status == "running")

            parts = []
            if done_count:
                parts.append(f"{done_count}完成")
            if running_count:
                parts.append(f"{running_count}进行中")
            if fail_count:
                parts.append(f"{fail_count}失败")
            pending = total - done_count - fail_count - running_count
            if pending > 0 and not self._finalized:
                parts.append(f"{pending}等待")

            pct = int(done_count / total * 100) if total else 0
            progress_text = f"**进度：** {done_count}/{total} ({pct}%) {' · '.join(parts)}"
            elements.append({"tag": "markdown", "content": progress_text})

            elements.append({"tag": "hr"})
            for i, s in enumerate(self._steps):
                icon = _STATUS_ICONS.get(s.status, "⏳")
                line = f"{icon} {s.name}"
                if s.detail:
                    line += f" — {s.detail}"
                elif s.status == "running" and s.started_at:
                    step_elapsed = int(time.time() - s.started_at)
                    line += f" ({step_elapsed}秒)"
                elements.append({"tag": "markdown", "content": line})

        if summary_override:
            elements.append({"tag": "hr"})
            display_summary = summary_override
            if len(display_summary) > 200:
                display_summary = display_summary[:200] + "..."
            elements.append({"tag": "markdown", "content": display_summary})
        elif self._current_tool and not self._finalized:
            elements.append({"tag": "hr"})
            elements.append({"tag": "note", "elements": [
                {"tag": "plain_text", "content": f"当前工具: {self._current_tool}"}
            ]})

        if self._finalized:
            template = "green" if "完成" in self._title else "red"
        else:
            template = "blue"

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"content": self._title, "tag": "plain_text"},
                "template": template,
            },
            "elements": elements,
        }

    async def _do_edit(self, summary_override: Optional[str] = None) -> None:
        """Actually call the Feishu edit API."""
        if not self._card_msg_id:
            return
        try:
            card = self._build_card(summary_override=summary_override)
            payload = json.dumps(card, ensure_ascii=False)
            body = self.adapter._build_update_message_body(
                msg_type="interactive", content=payload,
            )
            request = self.adapter._build_update_message_request(
                message_id=self._card_msg_id, request_body=body,
            )
            response = await asyncio.to_thread(
                self.adapter._client.im.v1.message.update, request,
            )
            result = self.adapter._finalize_send_result(response, "progress card edit failed")
            if not result.success:
                logger.debug("[progress-card] Edit failed: %s", result.error)
        except Exception as exc:
            logger.debug("[progress-card] _do_edit error: %s", exc)
