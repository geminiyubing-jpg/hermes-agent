"""Feishu Lark API request builder helpers.

Centralizes all SDK request / body construction with SimpleNamespace fallbacks.
Extracted from ``adapter.py`` during optimization to reduce its size and keep
builder logic in one place.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

# ---------------------------------------------------------------------------
# Optional lark_oapi SDK imports — same pattern as adapter.py
# ---------------------------------------------------------------------------

try:
    from lark_oapi.api.im.v1 import (
        CreateFileRequest,
        CreateFileRequestBody,
        CreateImageRequest,
        CreateImageRequestBody,
        CreateMessageRequest,
        CreateMessageRequestBody,
        GetChatRequest,
        GetMessageRequest,
        GetMessageResourceRequest,
        ReplyMessageRequest,
        ReplyMessageRequestBody,
        UpdateMessageRequest,
        UpdateMessageRequestBody,
    )
    from lark_oapi.api.application.v6 import GetApplicationRequest
except ImportError:
    # All SDK classes unavailable — every builder will fall back to SimpleNamespace.
    CreateFileRequest = None  # type: ignore[assignment,misc]
    CreateFileRequestBody = None  # type: ignore[assignment,misc]
    CreateImageRequest = None  # type: ignore[assignment,misc]
    CreateImageRequestBody = None  # type: ignore[assignment,misc]
    CreateMessageRequest = None  # type: ignore[assignment,misc]
    CreateMessageRequestBody = None  # type: ignore[assignment,misc]
    GetChatRequest = None  # type: ignore[assignment,misc]
    GetMessageRequest = None  # type: ignore[assignment,misc]
    GetMessageResourceRequest = None  # type: ignore[assignment,misc]
    ReplyMessageRequest = None  # type: ignore[assignment,misc]
    ReplyMessageRequestBody = None  # type: ignore[assignment,misc]
    UpdateMessageRequest = None  # type: ignore[assignment,misc]
    UpdateMessageRequestBody = None  # type: ignore[assignment,misc]
    GetApplicationRequest = None  # type: ignore[assignment,misc]


class FeishuRequestBuilderMixin:
    """Mixin providing Lark API request construction methods.

    All methods are ``@staticmethod`` — they carry no instance state and can
    be freely moved between Mixin classes without breaking anything.
    """

    @staticmethod
    def _build_get_chat_request(chat_id: str) -> Any:
        if GetChatRequest is not None:
            return GetChatRequest.builder().chat_id(chat_id).build()
        return SimpleNamespace(chat_id=chat_id)

    @staticmethod
    def _build_get_message_request(message_id: str) -> Any:
        if GetMessageRequest is not None:
            return GetMessageRequest.builder().message_id(message_id).build()
        return SimpleNamespace(message_id=message_id)

    @staticmethod
    def _build_message_resource_request(*, message_id: str, file_key: str, resource_type: str) -> Any:
        if GetMessageResourceRequest is not None:
            return (
                GetMessageResourceRequest.builder()
                .message_id(message_id)
                .file_key(file_key)
                .type(resource_type)
                .build()
            )
        return SimpleNamespace(message_id=message_id, file_key=file_key, type=resource_type)

    @staticmethod
    def _build_get_application_request(*, app_id: str, lang: str) -> Any:
        if GetApplicationRequest is not None:
            return (
                GetApplicationRequest.builder()
                .app_id(app_id)
                .lang(lang)
                .build()
            )
        return SimpleNamespace(app_id=app_id, lang=lang)

    @staticmethod
    def _build_reply_message_body(*, content: str, msg_type: str, reply_in_thread: bool, uuid_value: str) -> Any:
        if ReplyMessageRequestBody is not None:
            return (
                ReplyMessageRequestBody.builder()
                .content(content)
                .msg_type(msg_type)
                .reply_in_thread(reply_in_thread)
                .uuid(uuid_value)
                .build()
            )
        return SimpleNamespace(
            content=content,
            msg_type=msg_type,
            reply_in_thread=reply_in_thread,
            uuid=uuid_value,
        )

    @staticmethod
    def _build_reply_message_request(message_id: str, request_body: Any) -> Any:
        if ReplyMessageRequest is not None:
            return (
                ReplyMessageRequest.builder()
                .message_id(message_id)
                .request_body(request_body)
                .build()
            )
        return SimpleNamespace(message_id=message_id, request_body=request_body)

    @staticmethod
    def _build_update_message_body(*, msg_type: str, content: str) -> Any:
        if UpdateMessageRequestBody is not None:
            return (
                UpdateMessageRequestBody.builder()
                .msg_type(msg_type)
                .content(content)
                .build()
            )
        return SimpleNamespace(msg_type=msg_type, content=content)

    @staticmethod
    def _build_update_message_request(message_id: str, request_body: Any) -> Any:
        if UpdateMessageRequest is not None:
            return (
                UpdateMessageRequest.builder()
                .message_id(message_id)
                .request_body(request_body)
                .build()
            )
        return SimpleNamespace(message_id=message_id, request_body=request_body)

    @staticmethod
    def _build_create_message_body(*, receive_id: str, msg_type: str, content: str, uuid_value: str) -> Any:
        if CreateMessageRequestBody is not None:
            return (
                CreateMessageRequestBody.builder()
                .receive_id(receive_id)
                .msg_type(msg_type)
                .content(content)
                .uuid(uuid_value)
                .build()
            )
        return SimpleNamespace(
            receive_id=receive_id,
            msg_type=msg_type,
            content=content,
            uuid=uuid_value,
        )

    @staticmethod
    def _build_create_message_request(receive_id_type: str, request_body: Any) -> Any:
        if CreateMessageRequest is not None:
            return (
                CreateMessageRequest.builder()
                .receive_id_type(receive_id_type)
                .request_body(request_body)
                .build()
            )
        return SimpleNamespace(receive_id_type=receive_id_type, request_body=request_body)

    @staticmethod
    def _build_image_upload_body(*, image_type: str, image: Any) -> Any:
        if CreateImageRequestBody is not None:
            return (
                CreateImageRequestBody.builder()
                .image_type(image_type)
                .image(image)
                .build()
            )
        return SimpleNamespace(image_type=image_type, image=image)

    @staticmethod
    def _build_image_upload_request(request_body: Any) -> Any:
        if CreateImageRequest is not None:
            return CreateImageRequest.builder().request_body(request_body).build()
        return SimpleNamespace(request_body=request_body)

    @staticmethod
    def _build_file_upload_body(*, file_type: str, file_name: str, file: Any) -> Any:
        if CreateFileRequestBody is not None:
            return (
                CreateFileRequestBody.builder()
                .file_type(file_type)
                .file_name(file_name)
                .file(file)
                .build()
            )
        return SimpleNamespace(file_type=file_type, file_name=file_name, file=file)

    @staticmethod
    def _build_file_upload_request(request_body: Any) -> Any:
        if CreateFileRequest is not None:
            return CreateFileRequest.builder().request_body(request_body).build()
        return SimpleNamespace(request_body=request_body)
