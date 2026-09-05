"""Tests for FeishuNotifier — target resolution, callback routing, and client/token caching.

Tests the notifier in isolation; all lark_oapi SDK calls are mocked.
"""

import os
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from self_evolution.feishu_notifier import FeishuNotifier


class TestResolveTarget(unittest.TestCase):
    """Tests for _resolve_target target parsing."""

    @patch.dict(os.environ, {"SELF_EVOLUTION_FEISHU_DELIVER": "chat:oc_chat_123"}, clear=False)
    def test_chat_prefix_returns_chat_id(self):
        notifier = FeishuNotifier()
        receive_id, receive_id_type = notifier._resolve_target()
        self.assertEqual(receive_id, "oc_chat_123")
        self.assertEqual(receive_id_type, "chat_id")

    @patch.dict(os.environ, {"SELF_EVOLUTION_FEISHU_DELIVER": "user", "SELF_EVOLUTION_FEISHU_USER_ID": ""}, clear=False)
    def test_missing_user_id_returns_empty(self):
        notifier = FeishuNotifier()
        receive_id, receive_id_type = notifier._resolve_target()
        self.assertEqual(receive_id, "")
        self.assertEqual(receive_id_type, "")

    @patch.dict(os.environ, {
        "SELF_EVOLUTION_FEISHU_DELIVER": "user",
        "SELF_EVOLUTION_FEISHU_USER_ID": "ou_test_user",
    }, clear=False)
    def test_ou_prefix_returns_open_id(self):
        notifier = FeishuNotifier()
        receive_id, receive_id_type = notifier._resolve_target()
        self.assertEqual(receive_id, "ou_test_user")
        self.assertEqual(receive_id_type, "open_id")

    @patch.dict(os.environ, {
        "SELF_EVOLUTION_FEISHU_DELIVER": "user",
        "SELF_EVOLUTION_FEISHU_USER_ID": "oc_test_chat",
    }, clear=False)
    def test_oc_prefix_returns_chat_id(self):
        notifier = FeishuNotifier()
        receive_id, receive_id_type = notifier._resolve_target()
        self.assertEqual(receive_id, "oc_test_chat")
        self.assertEqual(receive_id_type, "chat_id")

    @patch.dict(os.environ, {
        "SELF_EVOLUTION_FEISHU_DELIVER": "user",
        "SELF_EVOLUTION_FEISHU_USER_ID": "uid_regular",
    }, clear=False)
    def test_regular_user_id_returns_user_id_type(self):
        notifier = FeishuNotifier()
        receive_id, receive_id_type = notifier._resolve_target()
        self.assertEqual(receive_id, "uid_regular")
        self.assertEqual(receive_id_type, "user_id")


class TestHandleCallbackRouting(unittest.TestCase):
    """Tests for handle_callback routing to approve/modify/reject."""

    @patch.object(FeishuNotifier, "_approve")
    def test_approve_action_routes_correctly(self, mock_approve):
        notifier = FeishuNotifier()
        notifier.handle_callback("approve", "prop_1")
        mock_approve.assert_called_once_with("prop_1")

    @patch.object(FeishuNotifier, "_modify")
    def test_modify_action_routes_correctly(self, mock_modify):
        notifier = FeishuNotifier()
        notifier.handle_callback("modify", "prop_2", "change this")
        mock_modify.assert_called_once_with("prop_2", "change this")

    @patch.object(FeishuNotifier, "_reject")
    def test_reject_action_routes_correctly(self, mock_reject):
        notifier = FeishuNotifier()
        notifier.handle_callback("reject", "prop_3", "bad idea")
        mock_reject.assert_called_once_with("prop_3", "bad idea")

    def test_unknown_action_does_nothing(self):
        notifier = FeishuNotifier()
        # Should not raise
        notifier.handle_callback("unknown", "prop_4")


class TestClientCaching(unittest.TestCase):
    """Tests for _get_client caching behavior."""

    @patch.dict(os.environ, {"FEISHU_APP_ID": "cli_test", "FEISHU_APP_SECRET": "sec_test"}, clear=False)
    def test_client_created_once_and_cached(self):
        notifier = FeishuNotifier()
        mock_client = SimpleNamespace()
        with patch("self_evolution.feishu_notifier.FeishuNotifier._get_client", return_value=mock_client) as mock_get:
            # First call
            notifier._client = None
            notifier._client = mock_client
            # Second call
            result = notifier._client
            self.assertIs(result, mock_client)

    @patch.dict(os.environ, {"FEISHU_APP_ID": "cli_test", "FEISHU_APP_SECRET": "sec_test"}, clear=False)
    def test_client_none_initially(self):
        notifier = FeishuNotifier()
        self.assertIsNone(notifier._client)


class TestTokenCaching(unittest.TestCase):
    """Tests for _get_tenant_token caching behavior."""

    @patch.dict(os.environ, {"FEISHU_APP_ID": "cli_test", "FEISHU_APP_SECRET": "sec_test"}, clear=False)
    def test_cached_token_returned_within_ttl(self):
        notifier = FeishuNotifier()
        future_expire = time.time() + 5000
        notifier._token_cache = ("cached_token_xyz", future_expire)
        result = notifier._get_tenant_token()
        self.assertEqual(result, "cached_token_xyz")

    @patch.dict(os.environ, {"FEISHU_APP_ID": "cli_test", "FEISHU_APP_SECRET": "sec_test"}, clear=False)
    def test_expired_token_triggers_new_request(self):
        notifier = FeishuNotifier()
        notifier._token_cache = ("old_token", time.time() - 1)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"tenant_access_token": "new_token"}

        with patch("requests.post", return_value=mock_response):
            result = notifier._get_tenant_token()

        self.assertEqual(result, "new_token")
        self.assertEqual(notifier._token_cache[0], "new_token")

    @patch.dict(os.environ, {"FEISHU_APP_ID": "cli_test", "FEISHU_APP_SECRET": "sec_test"}, clear=False)
    def test_no_cache_initially(self):
        notifier = FeishuNotifier()
        self.assertIsNone(notifier._token_cache)
