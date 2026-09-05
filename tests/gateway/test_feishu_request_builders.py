"""Tests for FeishuRequestBuilderMixin — request/body construction with correct attribute values.

When the lark_oapi SDK is available, methods return real SDK objects with the expected
attributes. When the SDK is unavailable, they fall back to SimpleNamespace objects.
These tests verify that the returned objects always carry the correct attribute values
regardless of the SDK's presence.
"""

import unittest
from types import SimpleNamespace

from gateway.platforms.feishu.request_builders import FeishuRequestBuilderMixin


class TestBuildGetChatRequest(unittest.TestCase):
    """Tests for _build_get_chat_request."""

    def test_returns_object_with_chat_id(self):
        result = FeishuRequestBuilderMixin._build_get_chat_request("oc_test")
        self.assertEqual(result.chat_id, "oc_test")


class TestBuildGetMessageRequest(unittest.TestCase):
    """Tests for _build_get_message_request."""

    def test_returns_object_with_message_id(self):
        result = FeishuRequestBuilderMixin._build_get_message_request("om_123")
        self.assertEqual(result.message_id, "om_123")


class TestBuildMessageResourceRequest(unittest.TestCase):
    """Tests for _build_message_resource_request."""

    def test_returns_object_with_all_fields(self):
        result = FeishuRequestBuilderMixin._build_message_resource_request(
            message_id="om_1", file_key="fk_1", resource_type="image"
        )
        self.assertEqual(result.message_id, "om_1")
        self.assertEqual(result.file_key, "fk_1")
        self.assertEqual(result.type, "image")


class TestBuildGetApplicationRequest(unittest.TestCase):
    """Tests for _build_get_application_request."""

    def test_returns_object_with_app_id_and_lang(self):
        result = FeishuRequestBuilderMixin._build_get_application_request(
            app_id="cli_test", lang="zh"
        )
        self.assertEqual(result.app_id, "cli_test")
        self.assertEqual(result.lang, "zh")


class TestBuildReplyMessageBody(unittest.TestCase):
    """Tests for _build_reply_message_body."""

    def test_returns_object_with_all_fields(self):
        result = FeishuRequestBuilderMixin._build_reply_message_body(
            content='{"text":"hi"}', msg_type="text",
            reply_in_thread=True, uuid_value="uuid_1",
        )
        self.assertEqual(result.content, '{"text":"hi"}')
        self.assertEqual(result.msg_type, "text")
        self.assertTrue(result.reply_in_thread)
        self.assertEqual(result.uuid, "uuid_1")


class TestBuildReplyMessageRequest(unittest.TestCase):
    """Tests for _build_reply_message_request."""

    def test_returns_object_with_message_id_and_body(self):
        body = SimpleNamespace(content="test")
        result = FeishuRequestBuilderMixin._build_reply_message_request("om_1", body)
        self.assertEqual(result.message_id, "om_1")
        self.assertIs(result.request_body, body)


class TestBuildUpdateMessageBody(unittest.TestCase):
    """Tests for _build_update_message_body."""

    def test_returns_object_with_msg_type_and_content(self):
        result = FeishuRequestBuilderMixin._build_update_message_body(
            msg_type="interactive", content='{"card":{}}'
        )
        self.assertEqual(result.msg_type, "interactive")
        self.assertEqual(result.content, '{"card":{}}')


class TestBuildUpdateMessageRequest(unittest.TestCase):
    """Tests for _build_update_message_request."""

    def test_returns_object_with_message_id_and_body(self):
        body = SimpleNamespace(msg_type="text", content="hello")
        result = FeishuRequestBuilderMixin._build_update_message_request("om_2", body)
        self.assertEqual(result.message_id, "om_2")
        self.assertIs(result.request_body, body)


class TestBuildCreateMessageBody(unittest.TestCase):
    """Tests for _build_create_message_body."""

    def test_returns_object_with_all_fields(self):
        result = FeishuRequestBuilderMixin._build_create_message_body(
            receive_id="oc_chat", msg_type="text",
            content='{"text":"hello"}', uuid_value="uuid_2",
        )
        self.assertEqual(result.receive_id, "oc_chat")
        self.assertEqual(result.msg_type, "text")
        self.assertEqual(result.content, '{"text":"hello"}')
        self.assertEqual(result.uuid, "uuid_2")


class TestBuildCreateMessageRequest(unittest.TestCase):
    """Tests for _build_create_message_request."""

    def test_returns_object_with_receive_id_type_and_body(self):
        body = SimpleNamespace(content="test")
        result = FeishuRequestBuilderMixin._build_create_message_request("chat_id", body)
        self.assertEqual(result.receive_id_type, "chat_id")
        self.assertIs(result.request_body, body)


class TestBuildImageUploadBody(unittest.TestCase):
    """Tests for _build_image_upload_body."""

    def test_returns_object_with_image_type_and_image(self):
        result = FeishuRequestBuilderMixin._build_image_upload_body(
            image_type="message", image=b"fake_image_data"
        )
        self.assertEqual(result.image_type, "message")
        self.assertEqual(result.image, b"fake_image_data")


class TestBuildImageUploadRequest(unittest.TestCase):
    """Tests for _build_image_upload_request."""

    def test_returns_object_with_request_body(self):
        body = SimpleNamespace(image_type="message")
        result = FeishuRequestBuilderMixin._build_image_upload_request(body)
        self.assertIs(result.request_body, body)


class TestBuildFileUploadBody(unittest.TestCase):
    """Tests for _build_file_upload_body."""

    def test_returns_object_with_all_fields(self):
        result = FeishuRequestBuilderMixin._build_file_upload_body(
            file_type="pdf", file_name="report.pdf", file=b"fake_file_data"
        )
        self.assertEqual(result.file_type, "pdf")
        self.assertEqual(result.file_name, "report.pdf")
        self.assertEqual(result.file, b"fake_file_data")


class TestBuildFileUploadRequest(unittest.TestCase):
    """Tests for _build_file_upload_request."""

    def test_returns_object_with_request_body(self):
        body = SimpleNamespace(file_type="pdf")
        result = FeishuRequestBuilderMixin._build_file_upload_request(body)
        self.assertIs(result.request_body, body)
