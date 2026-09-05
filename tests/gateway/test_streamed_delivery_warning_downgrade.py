"""Duplicate-send diagnostic downgrade for commentary-only stream consumers.

With ``display.streaming: false`` the stream consumer still exists — it delivers
interim assistant commentary — but never receives deltas. A turn without
commentary leaves every delivery flag legitimately False, and the old
unconditional WARNING ("possible duplicate send") fired on every such turn.
The consumer having nothing visible to duplicate is the expected case: log it
at DEBUG, and keep the WARNING only when visible stream text exists (the real
ack-race signal the diagnostic was built for).
"""

import asyncio
import logging
from types import SimpleNamespace

import pytest

from gateway.config import GatewayConfig
from gateway.run import GatewayRunner
from gateway.turn_context import TurnContext


def _turn_ctx(stream_consumer) -> TurnContext:
    return TurnContext(
        source=SimpleNamespace(chat_id="c1"),
        session_key="agent:main:feishu:dm:c1",
        stream_consumer_holder=[stream_consumer],
    )


async def _run(sc, caplog):
    runner = GatewayRunner.__new__(GatewayRunner)  # skip __init__ (no config IO)
    response = {"final_response": "the answer", "response_previewed": False}
    with caplog.at_level(logging.DEBUG, logger="gateway.run"):
        await runner._run_agent_mark_streamed_delivery(response, _turn_ctx(sc))
    return response


def _no_visible_text_consumer() -> SimpleNamespace:
    """A consumer that never streamed and delivered no commentary/segments."""
    return SimpleNamespace(
        final_response_sent=False,
        final_content_delivered=False,
        message_id=None,
        _last_sent_text="",
        _accumulated="",
        _delivered_commentary_texts=[],
        _delivered_segment_texts=[],
    )


class TestCommentaryOnlyConsumerNoWarning:
    def test_streaming_off_commentary_free_turn_logs_debug_not_warning(self, caplog):
        sc = _no_visible_text_consumer()
        response = asyncio.run(_run(sc, caplog))
        assert response.get("already_sent") is not True  # normal send stays owner
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert any("no visible stream text" in r.message for r in caplog.records)

    def test_interim_commentary_delivered_still_no_duplicate_warning(self, caplog):
        # Commentary was sent, but it is not the final response — the normal
        # final send is still the sole delivery of the answer: no WARNING.
        sc = _no_visible_text_consumer()
        sc._delivered_commentary_texts = ["先查一下进度..."]
        response = asyncio.run(_run(sc, caplog))
        assert response.get("already_sent") is not True
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


class TestVisibleStreamTextKeepsWarning:
    def test_partial_stream_without_flags_still_warns(self, caplog):
        # The real duplicate-risk signal: text WAS shown but no delivery flag
        # confirms the final — keep the WARNING for the ack-race investigation.
        sc = _no_visible_text_consumer()
        sc._last_sent_text = "partial answer befor"
        response = asyncio.run(_run(sc, caplog))
        assert response.get("already_sent") is not True
        warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert warnings and "possible duplicate send" in warnings[0].message
