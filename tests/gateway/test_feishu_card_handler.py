"""Tests for FeishuCardHandlerMixin — card action dedup, approval card build, and loop acceptance.

Tests the mixin in isolation without requiring a real lark_oapi SDK installation.
All SDK objects are mocked.
"""

import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from gateway.platforms.feishu.card_handler import FeishuCardHandlerMixin
from gateway.platforms.feishu.constants import (
    _APPROVAL_LABEL_MAP,
    _FEISHU_CARD_ACTION_DEDUP_TTL_SECONDS,
)


def _make_handler(**overrides):
    """Build a minimal FeishuCardHandlerMixin instance with required attributes."""
    handler = FeishuCardHandlerMixin()
    handler._card_action_tokens = {}
    for k, v in overrides.items():
        setattr(handler, k, v)
    return handler


class TestIsCardActionDuplicate(unittest.TestCase):
    """Tests for _is_card_action_duplicate dedup logic."""

    def test_first_token_returns_false(self):
        handler = _make_handler()
        result = handler._is_card_action_duplicate("token_a")
        self.assertFalse(result)
        # Token should now be recorded
        self.assertIn("token_a", handler._card_action_tokens)

    def test_duplicate_token_returns_true(self):
        handler = _make_handler()
        handler._is_card_action_duplicate("token_b")
        result = handler._is_card_action_duplicate("token_b")
        self.assertTrue(result)

    def test_different_tokens_are_independent(self):
        handler = _make_handler()
        handler._is_card_action_duplicate("token_1")
        result = handler._is_card_action_duplicate("token_2")
        self.assertFalse(result)

    def test_expired_tokens_get_cleaned_on_large_dict(self):
        """When the token dict exceeds 256 entries, expired ones should be pruned."""
        handler = _make_handler()
        now = time.time()
        # Pre-populate with 257 expired entries to trigger cleanup
        expired_ts = now - _FEISHU_CARD_ACTION_DEDUP_TTL_SECONDS - 10
        for i in range(257):
            handler._card_action_tokens[f"old_{i}"] = expired_ts

        # Insert a valid (non-expired) entry
        handler._card_action_tokens["valid"] = now
        self.assertTrue(handler._is_card_action_duplicate("valid"))

        # A new token should return False, and some expired should have been cleaned
        result = handler._is_card_action_duplicate("new_token")
        self.assertFalse(result)
        # At least some old entries should have been evicted
        remaining_old = sum(1 for k in handler._card_action_tokens if k.startswith("old_"))
        self.assertLess(remaining_old, 257)


class TestBuildResolvedApprovalCard(unittest.TestCase):
    """Tests for _build_resolved_approval_card static method."""

    def test_deny_choice_uses_red_template_and_cross_icon(self):
        card = FeishuCardHandlerMixin._build_resolved_approval_card(
            choice="deny", user_name="Alice"
        )
        self.assertEqual(card["header"]["template"], "red")
        self.assertIn("❌", card["header"]["title"]["content"])
        self.assertEqual(
            card["elements"][0]["content"],
            "❌ **Denied** by Alice",
        )

    def test_approve_choice_uses_green_template_and_check_icon(self):
        card = FeishuCardHandlerMixin._build_resolved_approval_card(
            choice="once", user_name="Bob"
        )
        self.assertEqual(card["header"]["template"], "green")
        self.assertIn("✅", card["header"]["title"]["content"])
        label = _APPROVAL_LABEL_MAP.get("once", "Resolved")
        self.assertIn(label, card["elements"][0]["content"])
        self.assertIn("Bob", card["elements"][0]["content"])

    def test_card_structure_has_required_keys(self):
        card = FeishuCardHandlerMixin._build_resolved_approval_card(
            choice="deny", user_name="Charlie"
        )
        self.assertIn("config", card)
        self.assertIn("header", card)
        self.assertIn("elements", card)
        self.assertTrue(card["config"]["wide_screen_mode"])


class TestLoopAcceptsCallbacks(unittest.TestCase):
    """Tests for _loop_accepts_callbacks static method."""

    def test_normal_loop_returns_true(self):
        loop = SimpleNamespace(is_closed=lambda: False)
        self.assertTrue(FeishuCardHandlerMixin._loop_accepts_callbacks(loop))

    def test_none_loop_returns_false(self):
        self.assertFalse(FeishuCardHandlerMixin._loop_accepts_callbacks(None))

    def test_closed_loop_returns_false(self):
        loop = SimpleNamespace(is_closed=lambda: True)
        self.assertFalse(FeishuCardHandlerMixin._loop_accepts_callbacks(loop))


class TestOnCardActionTriggerRouting(unittest.TestCase):
    """Tests for _on_card_action_trigger event routing."""

    def test_drops_card_action_when_loop_not_ready(self):
        handler = _make_handler(_loop=None)
        # Should not raise; loop is not ready
        data = SimpleNamespace(event=SimpleNamespace(
            action=SimpleNamespace(value={}),
        ))
        result = handler._on_card_action_trigger(data)
        # Returns P2CardActionTriggerResponse or None depending on SDK availability
        # Just verify it doesn't crash

    def test_hermes_action_routed_to_approval_handler(self):
        handler = _make_handler(
            _loop=SimpleNamespace(is_closed=lambda: False),
        )
        handler._get_cached_sender_name = Mock(return_value="TestUser")
        handler._submit_on_loop = Mock()

        action_value = {"hermes_action": "approve_once", "approval_id": "123"}
        event = SimpleNamespace(
            action=SimpleNamespace(value=action_value),
            operator=SimpleNamespace(open_id="ou_test"),
        )
        data = SimpleNamespace(event=event)

        with patch.object(handler, "_handle_approval_card_action") as mock_approval:
            mock_approval.return_value = None
            handler._on_card_action_trigger(data)
            mock_approval.assert_called_once()

    def test_proposal_id_routed_to_evolution_handler(self):
        handler = _make_handler(
            _loop=SimpleNamespace(is_closed=lambda: False),
        )
        handler._get_cached_sender_name = Mock(return_value="TestUser")
        handler._submit_on_loop = Mock()

        action_value = {"proposal_id": "prop_123", "action": "approve"}
        event = SimpleNamespace(
            action=SimpleNamespace(value=action_value),
            operator=SimpleNamespace(open_id="ou_test"),
        )
        data = SimpleNamespace(event=event)

        with patch.object(handler, "_handle_evolution_card_action") as mock_evo:
            mock_evo.return_value = None
            handler._on_card_action_trigger(data)
            mock_evo.assert_called_once()
