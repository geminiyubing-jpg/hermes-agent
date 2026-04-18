"""
Self Evolution Plugin — Feishu Notifier
========================================

Pushes evolution proposals to Feishu at 19:00 daily.
Uses interactive card messages with action buttons for approval.

Receives callbacks when user clicks: approve / modify / reject.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from self_evolution import db
from self_evolution.models import Proposal

logger = logging.getLogger(__name__)


class FeishuNotifier:
    """Send evolution proposals via Feishu interactive cards."""

    def __init__(self):
        self.app_id = os.getenv("FEISHU_APP_ID", "")
        self.app_secret = os.getenv("FEISHU_APP_SECRET", "")
        self.enabled = bool(self.app_id and self.app_secret)

    def send_daily_report(self):
        """Send pending proposals as a daily Feishu card message.

        Called by the 19:00 cron job.
        """
        if not self.enabled:
            logger.info("Feishu not configured, skipping notification")
            return

        # Load pending proposals
        proposals = db.fetch_all(
            "evolution_proposals",
            where="status = ?",
            params=("pending_approval",),
            order_by="created_at DESC",
        )

        if not proposals:
            logger.info("No pending proposals to send")
            return

        # Load latest reflection report for context
        reports = db.fetch_all(
            "reflection_reports",
            order_by="created_at DESC",
            limit=1,
        )
        report = reports[0] if reports else {}

        # Build card
        card = self._build_card(proposals, report)

        # Send
        self._send_card(card)
        logger.info("Sent %d proposals via Feishu", len(proposals))

    def handle_callback(self, action: str, proposal_id: str, user_input: str = ""):
        """Handle Feishu card button callback.

        Args:
            action: "approve" | "modify" | "reject"
            proposal_id: The proposal ID
            user_input: Optional user modification text
        """
        if action == "approve":
            self._approve(proposal_id)
        elif action == "modify":
            self._modify(proposal_id, user_input)
        elif action == "reject":
            self._reject(proposal_id, user_input)

    def send_rollback_notification(self, unit_id: str, reason: str):
        """Notify user that an improvement unit was auto-rolled back."""
        if not self.enabled:
            return
        card = {
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**自动回滚通知**\n\n"
                                   f"改进单元 `{unit_id}` 已自动回滚。\n"
                                   f"原因: {reason}",
                    },
                },
            ],
        }
        self._send_card(card)

    # ── Internal Methods ──────────────────────────────────────────────────

    def _approve(self, proposal_id: str):
        """Mark proposal as approved and trigger execution."""
        db.update(
            "evolution_proposals",
            {"status": "approved", "resolved_at": time.time()},
            where="id = ?",
            where_params=(proposal_id,),
        )

        # Trigger execution
        from self_evolution.evolution_executor import EvolutionExecutor
        executor = EvolutionExecutor()
        row = db.fetch_one("evolution_proposals", where="id = ?", params=(proposal_id,))
        if row:
            proposal = Proposal(
                id=row["id"],
                proposal_type=row["proposal_type"],
                title=row["title"],
                description=row["description"],
                expected_impact=row.get("expected_impact", ""),
                risk_assessment=row.get("risk_assessment", "low"),
                rollback_plan=row.get("rollback_plan", ""),
                status="approved",
            )
            executor.execute(proposal)

        self._send_confirmation(proposal_id, "已执行")

    def _modify(self, proposal_id: str, user_input: str):
        """Update proposal with user's modification."""
        db.update(
            "evolution_proposals",
            {"user_feedback": user_input, "status": "pending_approval"},
            where="id = ?",
            where_params=(proposal_id,),
        )
        self._send_confirmation(proposal_id, "已修改，等待重新确认")

    def _reject(self, proposal_id: str, user_input: str):
        """Mark proposal as rejected and record reason for learning."""
        db.update(
            "evolution_proposals",
            {"status": "rejected", "user_feedback": user_input, "resolved_at": time.time()},
            where="id = ?",
            where_params=(proposal_id,),
        )
        # Record rejection for the dream engine to learn from
        db.insert("outcome_signals", {
            "session_id": f"evolution_rejection_{proposal_id}",
            "signal_type": "proposal_rejected",
            "signal_value": 0.0,
            "metadata": json.dumps({"proposal_id": proposal_id, "reason": user_input}, ensure_ascii=False),
        })

    def _build_card(self, proposals: List[dict], report: dict) -> dict:
        """Build Feishu interactive card JSON."""
        # Header
        date_str = time.strftime("%Y-%m-%d", time.localtime())
        elements = []

        # Overview section
        sessions_analyzed = report.get("sessions_analyzed", 0)
        avg_score = report.get("avg_score", 0)
        overview = (
            f"**日期**: {date_str}\n"
            f"**分析Sessions**: {sessions_analyzed}\n"
            f"**平均评分**: {avg_score:.3f}\n"
        )
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": overview},
        })

        # Error summary
        error_summary = report.get("error_summary", "")
        if error_summary:
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**错误分析**\n{error_summary}"},
            })

        # Waste summary
        waste_summary = report.get("waste_summary", "")
        if waste_summary:
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"**时间浪费分析**\n{waste_summary}"},
            })

        # Separator
        elements.append({"tag": "hr"})

        # Proposals
        for i, p in enumerate(proposals):
            type_emoji = {"skill": "🛠️", "strategy": "⚡", "memory": "🧠", "tool_preference": "🔧"}
            emoji = type_emoji.get(p.get("proposal_type", ""), "📋")

            proposal_text = (
                f"**[{emoji}] {p.get('title', f'提案 {i+1}')}**\n"
                f"{p.get('description', '')[:200]}\n"
                f"预期影响: {p.get('expected_impact', 'N/A')} | "
                f"风险: {p.get('risk_assessment', 'low')}\n"
            )
            elements.append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": proposal_text},
            })

            # Action buttons
            elements.append({
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "通过"},
                        "type": "primary",
                        "value": {"action": "approve", "proposal_id": p["id"]},
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "修改"},
                        "type": "default",
                        "value": {"action": "modify", "proposal_id": p["id"]},
                    },
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "拒绝"},
                        "type": "danger",
                        "value": {"action": "reject", "proposal_id": p["id"]},
                    },
                ],
            })

        return {
            "header": {
                "title": {"tag": "plain_text", "content": f"Hermes 每日进化报告 ({date_str})"},
                "template": "blue",
            },
            "elements": elements,
        }

    def _send_card(self, card: dict):
        """Send an interactive card via Feishu.

        Uses the existing Feishu gateway if available,
        otherwise falls back to direct API call.
        """
        try:
            # Try using existing gateway's send_message
            import requests

            # Get tenant access token
            token = self._get_tenant_token()
            if not token:
                logger.warning("Failed to get Feishu token")
                return

            # Send card message
            deliver_to = os.getenv("SELF_EVOLUTION_FEISHU_DELIVER", "user")
            url = "https://open.feishu.cn/open-apis/im/v1/messages"

            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }

            payload = {
                "msg_type": "interactive",
                "content": json.dumps(card, ensure_ascii=False),
            }

            if deliver_to.startswith("chat:"):
                payload["receive_id"] = deliver_to.replace("chat:", "")
                payload["receive_id_type"] = "chat_id"
            else:
                # Send to user
                user_id = os.getenv("SELF_EVOLUTION_FEISHU_USER_ID", "")
                if user_id:
                    payload["receive_id"] = user_id
                    payload["receive_id_type"] = "user_id"

            resp = requests.post(url, headers=headers, params=payload, timeout=30)
            if resp.status_code != 200:
                logger.warning("Feishu send failed: %s", resp.text)

        except Exception as exc:
            logger.warning("Feishu notification failed: %s", exc)

    def _send_confirmation(self, proposal_id: str, message: str):
        """Send a simple confirmation message."""
        if not self.enabled:
            return
        card = {
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**提案 `{proposal_id}`**: {message}",
                    },
                },
            ],
        }
        self._send_card(card)

    def _get_tenant_token(self) -> Optional[str]:
        """Get Feishu tenant access token."""
        try:
            import requests
            resp = requests.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={
                    "app_id": self.app_id,
                    "app_secret": self.app_secret,
                },
                timeout=10,
            )
            if resp.status_code == 200:
                return resp.json().get("tenant_access_token")
        except Exception as exc:
            logger.debug("Failed to get Feishu token: %s", exc)
        return None
