"""Tests for FeishuWebhookMixin — rate limiting, signature verification, and anomaly tracking.

Tests the mixin in isolation without requiring aiohttp or lark_oapi SDK.
"""

import hashlib
import hmac
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from gateway.platforms.feishu.webhook import FeishuWebhookMixin
from gateway.platforms.feishu.constants import (
    _FEISHU_WEBHOOK_RATE_LIMIT_MAX,
    _FEISHU_WEBHOOK_RATE_WINDOW_SECONDS,
    _FEISHU_WEBHOOK_ANOMALY_THRESHOLD,
    _FEISHU_WEBHOOK_ANOMALY_TTL_SECONDS,
    _FEISHU_WEBHOOK_ANOMALY_MAX_KEYS,
)


def _make_mixin(encrypt_key="", app_id="cli_test", webhook_path="/hook"):
    """Build a minimal FeishuWebhookMixin instance."""
    mixin = FeishuWebhookMixin()
    mixin._encrypt_key = encrypt_key
    mixin._app_id = app_id
    mixin._webhook_path = webhook_path
    mixin._webhook_rate_counts = {}
    mixin._webhook_anomaly_counts = {}
    mixin._webhook_runner = None
    mixin._webhook_site = None
    mixin._verification_token = ""
    return mixin


class TestCheckWebhookRateLimit(unittest.TestCase):
    """Tests for _check_webhook_rate_limit."""

    def test_normal_requests_allowed(self):
        mixin = _make_mixin()
        for _ in range(10):
            self.assertTrue(mixin._check_webhook_rate_limit("key_1"))

    def test_exceeding_limit_is_rejected(self):
        mixin = _make_mixin()
        for _ in range(_FEISHU_WEBHOOK_RATE_LIMIT_MAX):
            mixin._check_webhook_rate_limit("key_2")
        self.assertFalse(mixin._check_webhook_rate_limit("key_2"))

    def test_window_reset_allows_new_requests(self):
        mixin = _make_mixin()
        key = "key_3"
        for _ in range(_FEISHU_WEBHOOK_RATE_LIMIT_MAX):
            mixin._check_webhook_rate_limit(key)
        self.assertFalse(mixin._check_webhook_rate_limit(key))

        # Simulate window expiry
        count, window_start = mixin._webhook_rate_counts[key]
        mixin._webhook_rate_counts[key] = (
            count,
            window_start - _FEISHU_WEBHOOK_RATE_WINDOW_SECONDS - 1,
        )
        self.assertTrue(mixin._check_webhook_rate_limit(key))

    def test_different_keys_are_independent(self):
        mixin = _make_mixin()
        for _ in range(_FEISHU_WEBHOOK_RATE_LIMIT_MAX):
            mixin._check_webhook_rate_limit("key_a")
        self.assertFalse(mixin._check_webhook_rate_limit("key_a"))
        # Different key should still be allowed
        self.assertTrue(mixin._check_webhook_rate_limit("key_b"))


class TestIsWebhookSignatureValid(unittest.TestCase):
    """Tests for _is_webhook_signature_valid."""

    def test_valid_signature_passes(self):
        encrypt_key = "test_secret_key"
        mixin = _make_mixin(encrypt_key=encrypt_key)
        body = b'{"type":"event","data":"hello"}'
        timestamp = "1700000000"
        nonce = "nonce_abc"
        content = f"{timestamp}{nonce}{encrypt_key}{body.decode('utf-8')}"
        computed = hashlib.sha256(content.encode("utf-8")).hexdigest()
        headers = {
            "x-lark-request-timestamp": timestamp,
            "x-lark-request-nonce": nonce,
            "x-lark-signature": computed,
        }
        self.assertTrue(mixin._is_webhook_signature_valid(headers, body))

    def test_invalid_signature_rejected(self):
        mixin = _make_mixin(encrypt_key="secret")
        headers = {
            "x-lark-request-timestamp": "1700000000",
            "x-lark-request-nonce": "abc",
            "x-lark-signature": "deadbeef" * 8,
        }
        self.assertFalse(mixin._is_webhook_signature_valid(headers, b'{}'))

    def test_missing_headers_rejected(self):
        mixin = _make_mixin(encrypt_key="secret")
        self.assertFalse(mixin._is_webhook_signature_valid({}, b'{}'))

    def test_partial_headers_rejected(self):
        mixin = _make_mixin(encrypt_key="secret")
        # Only timestamp, missing nonce and signature
        headers = {"x-lark-request-timestamp": "1700000000"}
        self.assertFalse(mixin._is_webhook_signature_valid(headers, b'{}'))

    def test_no_encrypt_key_bypasses_check(self):
        mixin = _make_mixin(encrypt_key="")
        # _is_webhook_signature_valid is only called when encrypt_key is set,
        # but the method itself should still return False for missing headers
        self.assertFalse(mixin._is_webhook_signature_valid({}, b'{}'))


class TestRecordWebhookAnomaly(unittest.TestCase):
    """Tests for _record_webhook_anomaly and _clear_webhook_anomaly."""

    def test_first_record_starts_counter(self):
        mixin = _make_mixin()
        mixin._record_webhook_anomaly("10.0.0.1", "401")
        self.assertIn("10.0.0.1", mixin._webhook_anomaly_counts)
        count, status, _ = mixin._webhook_anomaly_counts["10.0.0.1"]
        self.assertEqual(count, 1)
        self.assertEqual(status, "401")

    def test_increment_within_ttl(self):
        mixin = _make_mixin()
        mixin._record_webhook_anomaly("10.0.0.2", "400")
        mixin._record_webhook_anomaly("10.0.0.2", "400")
        count, status, _ = mixin._webhook_anomaly_counts["10.0.0.2"]
        self.assertEqual(count, 2)

    def test_expired_entry_resets_counter(self):
        mixin = _make_mixin()
        now = time.time()
        # Plant an expired entry
        mixin._webhook_anomaly_counts["10.0.0.3"] = (
            5, "400", now - _FEISHU_WEBHOOK_ANOMALY_TTL_SECONDS - 1
        )
        mixin._record_webhook_anomaly("10.0.0.3", "401")
        count, status, _ = mixin._webhook_anomaly_counts["10.0.0.3"]
        self.assertEqual(count, 1)
        self.assertEqual(status, "401")

    def test_clear_removes_entry(self):
        mixin = _make_mixin()
        mixin._record_webhook_anomaly("10.0.0.4", "400")
        self.assertIn("10.0.0.4", mixin._webhook_anomaly_counts)
        mixin._clear_webhook_anomaly("10.0.0.4")
        self.assertNotIn("10.0.0.4", mixin._webhook_anomaly_counts)

    def test_clear_nonexistent_is_noop(self):
        mixin = _make_mixin()
        # Should not raise
        mixin._clear_webhook_anomaly("10.0.0.99")

    def test_prunes_when_at_capacity(self):
        mixin = _make_mixin()
        now = time.time()
        # Fill to capacity
        for i in range(_FEISHU_WEBHOOK_ANOMALY_MAX_KEYS):
            mixin._webhook_anomaly_counts[f"10.0.1.{i}"] = (1, "400", now)
        # Adding one more should trigger pruning
        mixin._record_webhook_anomaly("10.0.9.9", "400")
        self.assertIn("10.0.9.9", mixin._webhook_anomaly_counts)
