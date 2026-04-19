"""Tests for FeishuBatchMixin — media and text batching compatibility checks and task rescheduling.

Tests the mixin in isolation; no real asyncio event loop or lark_oapi SDK required.
"""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from gateway.platforms.base import MessageEvent, MessageType
from gateway.platforms.feishu.batch import FeishuBatchMixin


def _make_event(
    message_type=MessageType.PHOTO,
    reply_to_message_id=None,
    reply_to_text=None,
    thread_id=None,
    media_urls=None,
    text="",
):
    """Create a minimal MessageEvent for batch tests."""
    source = SimpleNamespace(
        platform="feishu",
        chat_id="oc_test",
        chat_name="Test",
        chat_type="dm",
        user_id="ou_user",
        user_name="Test",
        thread_id=thread_id,
    )
    return MessageEvent(
        text=text,
        message_type=message_type,
        source=source,
        message_id="om_test",
        media_urls=media_urls or [],
        media_types=[],
        reply_to_message_id=reply_to_message_id,
        reply_to_text=reply_to_text,
    )


def _make_mixin(**overrides):
    """Build a minimal FeishuBatchMixin instance with required attributes."""
    mixin = FeishuBatchMixin()
    mixin._pending_media_batches = {}
    mixin._pending_media_batch_tasks = {}
    mixin._pending_text_batches = {}
    mixin._pending_text_batch_tasks = {}
    mixin._pending_text_batch_counts = {}
    mixin._media_batch_delay_seconds = 0.1
    mixin._text_batch_delay_seconds = 0.1
    mixin._text_batch_split_delay_seconds = 0.2
    mixin._text_batch_max_messages = 8
    mixin._text_batch_max_chars = 4000
    mixin._SPLIT_THRESHOLD = 4000
    mixin.config = SimpleNamespace(extra={})

    async def _noop_guard(event):
        pass

    mixin._handle_message_with_guards = _noop_guard
    for k, v in overrides.items():
        setattr(mixin, k, v)
    return mixin


class TestMediaBatchIsCompatible(unittest.TestCase):
    """Tests for _media_batch_is_compatible static method."""

    def test_same_type_is_compatible(self):
        existing = _make_event(message_type=MessageType.PHOTO)
        incoming = _make_event(message_type=MessageType.PHOTO)
        self.assertTrue(FeishuBatchMixin._media_batch_is_compatible(existing, incoming))

    def test_different_type_is_not_compatible(self):
        existing = _make_event(message_type=MessageType.PHOTO)
        incoming = _make_event(message_type=MessageType.VIDEO)
        self.assertFalse(FeishuBatchMixin._media_batch_is_compatible(existing, incoming))

    def test_different_reply_to_is_not_compatible(self):
        existing = _make_event(message_type=MessageType.PHOTO, reply_to_message_id="om_1")
        incoming = _make_event(message_type=MessageType.PHOTO, reply_to_message_id="om_2")
        self.assertFalse(FeishuBatchMixin._media_batch_is_compatible(existing, incoming))

    def test_different_thread_id_is_not_compatible(self):
        existing = _make_event(message_type=MessageType.PHOTO, thread_id="thread_1")
        incoming = _make_event(message_type=MessageType.PHOTO, thread_id="thread_2")
        self.assertFalse(FeishuBatchMixin._media_batch_is_compatible(existing, incoming))

    def test_same_reply_to_is_compatible(self):
        existing = _make_event(message_type=MessageType.DOCUMENT, reply_to_message_id="om_parent")
        incoming = _make_event(message_type=MessageType.DOCUMENT, reply_to_message_id="om_parent")
        self.assertTrue(FeishuBatchMixin._media_batch_is_compatible(existing, incoming))


class TestTextBatchIsCompatible(unittest.TestCase):
    """Tests for _text_batch_is_compatible static method."""

    def test_same_reply_to_is_compatible(self):
        existing = _make_event(message_type=MessageType.TEXT, reply_to_message_id="om_1")
        incoming = _make_event(message_type=MessageType.TEXT, reply_to_message_id="om_1")
        self.assertTrue(FeishuBatchMixin._text_batch_is_compatible(existing, incoming))

    def test_different_reply_to_is_not_compatible(self):
        existing = _make_event(message_type=MessageType.TEXT, reply_to_message_id="om_1")
        incoming = _make_event(message_type=MessageType.TEXT, reply_to_message_id="om_2")
        self.assertFalse(FeishuBatchMixin._text_batch_is_compatible(existing, incoming))

    def test_none_reply_to_is_compatible_with_none(self):
        existing = _make_event(message_type=MessageType.TEXT, reply_to_message_id=None)
        incoming = _make_event(message_type=MessageType.TEXT, reply_to_message_id=None)
        self.assertTrue(FeishuBatchMixin._text_batch_is_compatible(existing, incoming))

    def test_different_thread_id_is_not_compatible(self):
        existing = _make_event(message_type=MessageType.TEXT, thread_id="t1")
        incoming = _make_event(message_type=MessageType.TEXT, thread_id="t2")
        self.assertFalse(FeishuBatchMixin._text_batch_is_compatible(existing, incoming))


class TestRescheduleBatchTask(unittest.TestCase):
    """Tests for _reschedule_batch_task static method."""

    def test_cancels_prior_task_and_creates_new(self):
        task_map = {}
        prior_task = Mock()
        prior_task.done.return_value = False
        task_map["key_a"] = prior_task

        flush_fn = Mock()

        with patch("gateway.platforms.feishu.batch.asyncio.create_task") as mock_create:
            mock_create.return_value = "new_task"
            FeishuBatchMixin._reschedule_batch_task(task_map, "key_a", flush_fn)

        prior_task.cancel.assert_called_once()
        mock_create.assert_called_once()
        self.assertEqual(task_map["key_a"], "new_task")

    def test_no_cancel_when_prior_done(self):
        task_map = {}
        prior_task = Mock()
        prior_task.done.return_value = True
        task_map["key_b"] = prior_task

        with patch("gateway.platforms.feishu.batch.asyncio.create_task") as mock_create:
            mock_create.return_value = "new_task"
            FeishuBatchMixin._reschedule_batch_task(task_map, "key_b", Mock())

        prior_task.cancel.assert_not_called()

    def test_new_key_creates_task(self):
        task_map = {}
        flush_fn = Mock()

        with patch("gateway.platforms.feishu.batch.asyncio.create_task") as mock_create:
            mock_create.return_value = "new_task"
            FeishuBatchMixin._reschedule_batch_task(task_map, "new_key", flush_fn)

        mock_create.assert_called_once()
        self.assertEqual(task_map["new_key"], "new_task")


class TestShouldBatchMediaEvent(unittest.TestCase):
    """Tests for _should_batch_media_event."""

    def test_photo_with_media_urls_should_batch(self):
        mixin = _make_mixin()
        event = _make_event(message_type=MessageType.PHOTO, media_urls=["/tmp/a.png"])
        self.assertTrue(mixin._should_batch_media_event(event))

    def test_photo_without_media_urls_should_not_batch(self):
        mixin = _make_mixin()
        event = _make_event(message_type=MessageType.PHOTO, media_urls=[])
        self.assertFalse(mixin._should_batch_media_event(event))

    def test_text_with_media_urls_should_not_batch(self):
        mixin = _make_mixin()
        event = _make_event(message_type=MessageType.TEXT, media_urls=["/tmp/a.png"])
        self.assertFalse(mixin._should_batch_media_event(event))
