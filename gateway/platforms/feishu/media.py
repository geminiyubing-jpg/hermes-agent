"""Feishu media handling — upload, download, and content-extraction methods.

Extracted from ``gateway.platforms.feishu`` as a Mixin so that the main adapter
class remains focused on connection / routing logic while all media-related
helpers live together in one place.

The mixin expects the host class to provide ``self._client``, ``self._loop``,
and various builder / helper methods (e.g. ``_build_image_upload_body``,
``_feishu_send_with_retry``, etc.) that are resolved via normal ``self``
attribute lookup at runtime.
"""

from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import os
import re
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

from gateway.platforms.base import (
    MessageEvent,
    MessageType,
    SendResult,
    SUPPORTED_DOCUMENT_TYPES,
    cache_audio_from_bytes,
    cache_document_from_bytes,
    cache_image_from_bytes,
    cache_image_from_url,
)

from .constants import (
    _AUDIO_EXTENSIONS,
    _DOCUMENT_MIME_TO_EXT,
    _FEISHU_DOC_UPLOAD_TYPES,
    _FEISHU_FILE_UPLOAD_TYPE,
    _FEISHU_IMAGE_UPLOAD_TYPE,
    _FEISHU_MEDIA_UPLOAD_EXTENSIONS,
    _FEISHU_OPUS_UPLOAD_EXTENSIONS,
    _IMAGE_EXTENSIONS,
    _MAX_TEXT_INJECT_BYTES,
    _VIDEO_EXTENSIONS,
)
from .message_parser import normalize_feishu_message
from .types import FeishuNormalizedMessage

logger = logging.getLogger(__name__)


class FeishuMediaMixin:
    """Mixin providing all media upload / download / extraction helpers."""

    # =====================================================================
    # Public send helpers — voice, document, video, image, animation
    # =====================================================================

    async def send_voice(
        self,
        chat_id: str,
        audio_path: str,
        caption: Optional[str] = None,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> SendResult:
        """Send audio to Feishu as a file attachment plus optional caption."""
        return await self._send_uploaded_file_message(
            chat_id=chat_id,
            file_path=audio_path,
            reply_to=reply_to,
            metadata=metadata,
            caption=caption,
            outbound_message_type="audio",
        )

    async def send_document(
        self,
        chat_id: str,
        file_path: str,
        caption: Optional[str] = None,
        file_name: Optional[str] = None,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> SendResult:
        """Send a document/file attachment to Feishu."""
        return await self._send_uploaded_file_message(
            chat_id=chat_id,
            file_path=file_path,
            reply_to=reply_to,
            metadata=metadata,
            caption=caption,
            file_name=file_name,
        )

    async def send_video(
        self,
        chat_id: str,
        video_path: str,
        caption: Optional[str] = None,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> SendResult:
        """Send a video file to Feishu."""
        return await self._send_uploaded_file_message(
            chat_id=chat_id,
            file_path=video_path,
            reply_to=reply_to,
            metadata=metadata,
            caption=caption,
            outbound_message_type="media",
        )

    async def send_image_file(
        self,
        chat_id: str,
        image_path: str,
        caption: Optional[str] = None,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> SendResult:
        """Send a local image file to Feishu."""
        if not self._client:
            return SendResult(success=False, error="Not connected")
        if not os.path.exists(image_path):
            return SendResult(success=False, error=f"Image file not found: {image_path}")

        try:
            import io as _io
            with open(image_path, "rb") as f:
                image_bytes = f.read()
            # Wrap in BytesIO so lark SDK's MultipartEncoder can read .name and .tell()
            image_file = _io.BytesIO(image_bytes)
            image_file.name = os.path.basename(image_path)
            body = self._build_image_upload_body(
                image_type=_FEISHU_IMAGE_UPLOAD_TYPE,
                image=image_file,
            )
            request = self._build_image_upload_request(body)
            upload_response = await asyncio.to_thread(self._client.im.v1.image.create, request)
            image_key = self._extract_response_field(upload_response, "image_key")
            if not image_key:
                return self._response_error_result(
                    upload_response,
                    default_message="image upload failed",
                    override_error="Feishu image upload missing image_key",
                )

            if caption:
                post_payload = self._build_media_post_payload(
                    caption=caption,
                    media_tag={"tag": "img", "image_key": image_key},
                )
                message_response = await self._feishu_send_with_retry(
                    chat_id=chat_id,
                    msg_type="post",
                    payload=post_payload,
                    reply_to=reply_to,
                    metadata=metadata,
                )
            else:
                message_response = await self._feishu_send_with_retry(
                    chat_id=chat_id,
                    msg_type="image",
                    payload=json.dumps({"image_key": image_key}, ensure_ascii=False),
                    reply_to=reply_to,
                    metadata=metadata,
                )
            return self._finalize_send_result(message_response, "image send failed")
        except Exception as exc:
            logger.error("[Feishu] Failed to send image %s: %s", image_path, exc, exc_info=True)
            return SendResult(success=False, error=str(exc))

    async def send_image(
        self,
        chat_id: str,
        image_url: str,
        caption: Optional[str] = None,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        """Download a remote image then send it through the native Feishu image flow."""
        try:
            image_path = await self._download_remote_image(image_url)
        except Exception as exc:
            logger.error("[Feishu] Failed to download image %s: %s", image_url, exc, exc_info=True)
            return await super().send_image(
                chat_id=chat_id,
                image_url=image_url,
                caption=caption,
                reply_to=reply_to,
                metadata=metadata,
            )
        return await self.send_image_file(
            chat_id=chat_id,
            image_path=image_path,
            caption=caption,
            reply_to=reply_to,
            metadata=metadata,
        )

    async def send_animation(
        self,
        chat_id: str,
        animation_url: str,
        caption: Optional[str] = None,
        reply_to: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SendResult:
        """Feishu has no native GIF bubble; degrade to a downloadable file."""
        try:
            file_path, file_name = await self._download_remote_document(
                animation_url,
                default_ext=".gif",
                preferred_name="animation.gif",
            )
        except Exception as exc:
            logger.error("[Feishu] Failed to download animation %s: %s", animation_url, exc, exc_info=True)
            return await super().send_animation(
                chat_id=chat_id,
                animation_url=animation_url,
                caption=caption,
                reply_to=reply_to,
                metadata=metadata,
            )
        degraded_caption = f"[GIF downgraded to file]\n{caption}" if caption else "[GIF downgraded to file]"
        return await self.send_document(
            chat_id=chat_id,
            file_path=file_path,
            file_name=file_name,
            caption=degraded_caption,
            reply_to=reply_to,
            metadata=metadata,
        )

    # =====================================================================
    # Remote resource download helpers
    # =====================================================================

    async def _download_remote_image(self, image_url: str) -> str:
        ext = self._guess_remote_extension(image_url, default=".jpg")
        return await cache_image_from_url(image_url, ext=ext)

    async def _download_remote_document(
        self,
        file_url: str,
        *,
        default_ext: str,
        preferred_name: str,
    ) -> tuple[str, str]:
        from tools.url_safety import is_safe_url
        if not is_safe_url(file_url):
            raise ValueError(f"Blocked unsafe URL (SSRF protection): {file_url[:80]}")

        import httpx

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(
                file_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; HermesAgent/1.0)",
                    "Accept": "*/*",
                },
            )
            response.raise_for_status()
        filename = self._derive_remote_filename(
            file_url,
            content_type=str(response.headers.get("Content-Type", "")),
            default_name=preferred_name,
            default_ext=default_ext,
        )
        cached_path = cache_document_from_bytes(response.content, filename)
        return cached_path, filename

    @staticmethod
    def _guess_remote_extension(url: str, *, default: str) -> str:
        ext = Path((url or "").split("?", 1)[0]).suffix.lower()
        return ext if ext in (_IMAGE_EXTENSIONS | _AUDIO_EXTENSIONS | _VIDEO_EXTENSIONS | set(SUPPORTED_DOCUMENT_TYPES)) else default

    @staticmethod
    def _derive_remote_filename(file_url: str, *, content_type: str, default_name: str, default_ext: str) -> str:
        candidate = Path((file_url or "").split("?", 1)[0]).name or default_name
        ext = Path(candidate).suffix.lower()
        if not ext:
            guessed = mimetypes.guess_extension((content_type or "").split(";", 1)[0].strip().lower() or "") or default_ext
            candidate = f"{candidate}{guessed}"
        return candidate

    @staticmethod
    def _namespace_from_mapping(value: Any) -> Any:
        if isinstance(value, dict):
            return SimpleNamespace(**{key: FeishuMediaMixin._namespace_from_mapping(item) for key, item in value.items()})
        if isinstance(value, list):
            return [FeishuMediaMixin._namespace_from_mapping(item) for item in value]
        return value

    # =====================================================================
    # Inbound message content extraction
    # =====================================================================

    async def _extract_message_content(self, message: Any) -> tuple[str, MessageType, List[str], List[str]]:
        """Extract text and cached media from a normalized Feishu message."""
        raw_content = getattr(message, "content", "") or ""
        raw_type = getattr(message, "message_type", "") or ""
        message_id = str(getattr(message, "message_id", "") or "")
        logger.info("[Feishu] Received raw message type=%s message_id=%s", raw_type, message_id)

        normalized = normalize_feishu_message(message_type=raw_type, raw_content=raw_content)
        media_urls, media_types = await self._download_feishu_message_resources(
            message_id=message_id,
            normalized=normalized,
        )
        inbound_type = self._resolve_normalized_message_type(normalized, media_types)
        text = normalized.text_content

        if (
            inbound_type in {MessageType.DOCUMENT, MessageType.AUDIO, MessageType.VIDEO, MessageType.PHOTO}
            and len(media_urls) == 1
            and normalized.preferred_message_type in {"document", "audio"}
        ):
            injected = await self._maybe_extract_text_document(media_urls[0], media_types[0])
            if injected:
                text = injected

        return text, inbound_type, media_urls, media_types

    async def _download_feishu_message_resources(
        self,
        *,
        message_id: str,
        normalized: FeishuNormalizedMessage,
    ) -> tuple[List[str], List[str]]:
        media_urls: List[str] = []
        media_types: List[str] = []

        for image_key in normalized.image_keys:
            cached_path, media_type = await self._download_feishu_image(
                message_id=message_id,
                image_key=image_key,
            )
            if cached_path:
                media_urls.append(cached_path)
                media_types.append(media_type)

        for media_ref in normalized.media_refs:
            cached_path, media_type = await self._download_feishu_message_resource(
                message_id=message_id,
                file_key=media_ref.file_key,
                resource_type=media_ref.resource_type,
                fallback_filename=media_ref.file_name,
            )
            if cached_path:
                media_urls.append(cached_path)
                media_types.append(media_type)

        return media_urls, media_types

    @staticmethod
    def _resolve_media_message_type(media_type: str, *, default: MessageType) -> MessageType:
        normalized = (media_type or "").lower()
        if normalized.startswith("image/"):
            return MessageType.PHOTO
        if normalized.startswith("audio/"):
            return MessageType.AUDIO
        if normalized.startswith("video/"):
            return MessageType.VIDEO
        return default

    def _resolve_normalized_message_type(
        self,
        normalized: FeishuNormalizedMessage,
        media_types: List[str],
    ) -> MessageType:
        preferred = normalized.preferred_message_type
        if preferred == "photo":
            return self._resolve_media_message_type(media_types[0] if media_types else "", default=MessageType.PHOTO)
        if preferred == "audio":
            return self._resolve_media_message_type(media_types[0] if media_types else "", default=MessageType.AUDIO)
        if preferred == "document":
            return self._resolve_media_message_type(media_types[0] if media_types else "", default=MessageType.DOCUMENT)
        return MessageType.TEXT

    async def _maybe_extract_text_document(self, cached_path: str, media_type: str) -> str:
        if not cached_path or not media_type.startswith("text/"):
            return ""
        try:
            if os.path.getsize(cached_path) > _MAX_TEXT_INJECT_BYTES:
                return ""
            ext = Path(cached_path).suffix.lower()
            if ext not in {".txt", ".md"} and media_type not in {"text/plain", "text/markdown"}:
                return ""
            content = Path(cached_path).read_text(encoding="utf-8")
            display_name = self._display_name_from_cached_path(cached_path)
            return f"[Content of {display_name}]:\n{content}"
        except (OSError, UnicodeDecodeError):
            logger.warning("[Feishu] Failed to inject text document content from %s", cached_path, exc_info=True)
            return ""

    # =====================================================================
    # Feishu resource download & caching
    # =====================================================================

    async def _download_feishu_image(self, *, message_id: str, image_key: str) -> tuple[str, str]:
        if not self._client or not message_id:
            return "", ""
        try:
            request = self._build_message_resource_request(
                message_id=message_id,
                file_key=image_key,
                resource_type="image",
            )
            response = await asyncio.to_thread(self._client.im.v1.message_resource.get, request)
            if not response or not response.success():
                logger.warning(
                    "[Feishu] Failed to download image %s: %s %s",
                    image_key,
                    getattr(response, "code", "unknown"),
                    getattr(response, "msg", "request failed"),
                )
                return "", ""
            raw_bytes = self._read_binary_response(response)
            if not raw_bytes:
                return "", ""
            content_type = self._get_response_header(response, "Content-Type")
            filename = getattr(response, "file_name", None) or f"{image_key}.jpg"
            ext = self._guess_extension(filename, content_type, ".jpg", allowed=_IMAGE_EXTENSIONS)
            cached_path = cache_image_from_bytes(raw_bytes, ext=ext)
            media_type = self._normalize_media_type(content_type, default=self._default_image_media_type(ext))
            return cached_path, media_type
        except Exception:
            logger.warning("[Feishu] Failed to cache image resource %s", image_key, exc_info=True)
            return "", ""

    async def _download_feishu_message_resource(
        self,
        *,
        message_id: str,
        file_key: str,
        resource_type: str,
        fallback_filename: str,
    ) -> tuple[str, str]:
        if not self._client or not message_id:
            return "", ""

        request_types = [resource_type]
        if resource_type in {"audio", "media"}:
            request_types.append("file")

        for request_type in request_types:
            try:
                request = self._build_message_resource_request(
                    message_id=message_id,
                    file_key=file_key,
                    resource_type=request_type,
                )
                response = await asyncio.to_thread(self._client.im.v1.message_resource.get, request)
                if not response or not response.success():
                    logger.debug(
                        "[Feishu] Resource download failed for %s/%s via type=%s: %s %s",
                        message_id,
                        file_key,
                        request_type,
                        getattr(response, "code", "unknown"),
                        getattr(response, "msg", "request failed"),
                    )
                    continue

                raw_bytes = self._read_binary_response(response)
                if not raw_bytes:
                    continue
                content_type = self._get_response_header(response, "Content-Type")
                response_filename = getattr(response, "file_name", None) or ""
                filename = response_filename or fallback_filename or f"{request_type}_{file_key}"
                media_type = self._normalize_media_type(
                    content_type,
                    default=self._guess_media_type_from_filename(filename),
                )

                if media_type.startswith("image/"):
                    ext = self._guess_extension(filename, content_type, ".jpg", allowed=_IMAGE_EXTENSIONS)
                    cached_path = cache_image_from_bytes(raw_bytes, ext=ext)
                    logger.info("[Feishu] Cached message image resource at %s", cached_path)
                    return cached_path, media_type or self._default_image_media_type(ext)

                if request_type == "audio" or media_type.startswith("audio/"):
                    ext = self._guess_extension(filename, content_type, ".ogg", allowed=_AUDIO_EXTENSIONS)
                    cached_path = cache_audio_from_bytes(raw_bytes, ext=ext)
                    logger.info("[Feishu] Cached message audio resource at %s", cached_path)
                    return cached_path, (media_type or f"audio/{ext.lstrip('.') or 'ogg'}")

                if media_type.startswith("video/"):
                    if not Path(filename).suffix:
                        filename = f"{filename}.mp4"
                    cached_path = cache_document_from_bytes(raw_bytes, filename)
                    logger.info("[Feishu] Cached message video resource at %s", cached_path)
                    return cached_path, media_type

                if not Path(filename).suffix and media_type in _DOCUMENT_MIME_TO_EXT:
                    filename = f"{filename}{_DOCUMENT_MIME_TO_EXT[media_type]}"
                cached_path = cache_document_from_bytes(raw_bytes, filename)
                logger.info("[Feishu] Cached message document resource at %s", cached_path)
                return cached_path, (media_type or self._guess_document_media_type(filename))
            except Exception:
                logger.warning(
                    "[Feishu] Failed to cache message resource %s/%s",
                    message_id,
                    file_key,
                    exc_info=True,
                )
        return "", ""

    # =========================================================================
    # Static helpers — extension / media-type guessing
    # =========================================================================

    @staticmethod
    def _read_binary_response(response: Any) -> bytes:
        file_obj = getattr(response, "file", None)
        if file_obj is None:
            return b""
        if hasattr(file_obj, "getvalue"):
            return bytes(file_obj.getvalue())
        return bytes(file_obj.read())

    @staticmethod
    def _get_response_header(response: Any, name: str) -> str:
        raw = getattr(response, "raw", None)
        headers = getattr(raw, "headers", {}) or {}
        return str(headers.get(name, headers.get(name.lower(), "")) or "").split(";", 1)[0].strip().lower()

    @staticmethod
    def _guess_extension(filename: str, content_type: str, default: str, *, allowed: set[str]) -> str:
        ext = Path(filename or "").suffix.lower()
        if ext in allowed:
            return ext
        guessed = mimetypes.guess_extension((content_type or "").split(";", 1)[0].strip().lower() or "")
        if guessed in allowed:
            return guessed
        return default

    @staticmethod
    def _normalize_media_type(content_type: str, *, default: str) -> str:
        normalized = (content_type or "").split(";", 1)[0].strip().lower()
        return normalized or default

    @staticmethod
    def _guess_document_media_type(filename: str) -> str:
        ext = Path(filename or "").suffix.lower()
        return SUPPORTED_DOCUMENT_TYPES.get(ext, mimetypes.guess_type(filename or "")[0] or "application/octet-stream")

    @staticmethod
    def _display_name_from_cached_path(path: str) -> str:
        basename = os.path.basename(path)
        parts = basename.split("_", 2)
        display_name = parts[2] if len(parts) >= 3 else basename
        return re.sub(r"[^\w.\- ]", "_", display_name)

    @staticmethod
    def _guess_media_type_from_filename(filename: str) -> str:
        guessed = (mimetypes.guess_type(filename or "")[0] or "").lower()
        if guessed:
            return guessed
        ext = Path(filename or "").suffix.lower()
        if ext in _VIDEO_EXTENSIONS:
            return f"video/{ext.lstrip('.')}"
        if ext in _AUDIO_EXTENSIONS:
            return f"audio/{ext.lstrip('.')}"
        if ext in _IMAGE_EXTENSIONS:
            return FeishuMediaMixin._default_image_media_type(ext)
        return ""

    @staticmethod
    def _default_image_media_type(ext: str) -> str:
        normalized_ext = (ext or "").lower()
        if normalized_ext in {".jpg", ".jpeg"}:
            return "image/jpeg"
        return f"image/{normalized_ext.lstrip('.') or 'jpeg'}"

    # =====================================================================
    # Outbound file upload & send helpers
    # =====================================================================

    async def _send_uploaded_file_message(
        self,
        *,
        chat_id: str,
        file_path: str,
        reply_to: Optional[str],
        metadata: Optional[Dict[str, Any]],
        caption: Optional[str] = None,
        file_name: Optional[str] = None,
        outbound_message_type: str = "file",
    ) -> SendResult:
        if not self._client:
            return SendResult(success=False, error="Not connected")
        if not os.path.exists(file_path):
            return SendResult(success=False, error=f"File not found: {file_path}")

        display_name = file_name or os.path.basename(file_path)
        upload_file_type, resolved_message_type = self._resolve_outbound_file_routing(
            file_path=display_name,
            requested_message_type=outbound_message_type,
        )
        try:
            with open(file_path, "rb") as file_obj:
                body = self._build_file_upload_body(
                    file_type=upload_file_type,
                    file_name=display_name,
                    file=file_obj,
                )
                request = self._build_file_upload_request(body)
                upload_response = await asyncio.to_thread(self._client.im.v1.file.create, request)
            file_key = self._extract_response_field(upload_response, "file_key")
            if not file_key:
                return self._response_error_result(
                    upload_response,
                    default_message="file upload failed",
                    override_error="Feishu file upload missing file_key",
                )

            if caption:
                media_tag = {
                    "tag": "media",
                    "file_key": file_key,
                    "file_name": display_name,
                }
                message_response = await self._feishu_send_with_retry(
                    chat_id=chat_id,
                    msg_type="post",
                    payload=self._build_media_post_payload(caption=caption, media_tag=media_tag),
                    reply_to=reply_to,
                    metadata=metadata,
                )
            else:
                message_response = await self._feishu_send_with_retry(
                    chat_id=chat_id,
                    msg_type=resolved_message_type,
                    payload=json.dumps({"file_key": file_key}, ensure_ascii=False),
                    reply_to=reply_to,
                    metadata=metadata,
                )
            return self._finalize_send_result(message_response, "file send failed")
        except Exception as exc:
            logger.error("[Feishu] Failed to send file %s: %s", file_path, exc, exc_info=True)
            return SendResult(success=False, error=str(exc))

    async def _send_raw_message(
        self,
        *,
        chat_id: str,
        msg_type: str,
        payload: str,
        reply_to: Optional[str],
        metadata: Optional[Dict[str, Any]],
    ) -> Any:
        reply_in_thread = bool((metadata or {}).get("thread_id"))
        if reply_to:
            body = self._build_reply_message_body(
                content=payload,
                msg_type=msg_type,
                reply_in_thread=reply_in_thread,
                uuid_value=str(uuid.uuid4()),
            )
            request = self._build_reply_message_request(reply_to, body)
            return await asyncio.to_thread(self._client.im.v1.message.reply, request)

        body = self._build_create_message_body(
            receive_id=chat_id,
            msg_type=msg_type,
            content=payload,
            uuid_value=str(uuid.uuid4()),
        )
        request = self._build_create_message_request("chat_id", body)
        return await asyncio.to_thread(self._client.im.v1.message.create, request)

    # =====================================================================
    # Outbound file routing
    # =====================================================================

    @staticmethod
    def _resolve_outbound_file_routing(
        *,
        file_path: str,
        requested_message_type: str,
    ) -> tuple[str, str]:
        ext = Path(file_path).suffix.lower()

        if ext in _FEISHU_OPUS_UPLOAD_EXTENSIONS:
            return "opus", "audio"

        if ext in _FEISHU_MEDIA_UPLOAD_EXTENSIONS:
            return "mp4", "media"

        if ext in _FEISHU_DOC_UPLOAD_TYPES:
            return _FEISHU_DOC_UPLOAD_TYPES[ext], "file"

        if requested_message_type == "file":
            return _FEISHU_FILE_UPLOAD_TYPE, "file"

        return _FEISHU_FILE_UPLOAD_TYPE, "file"
