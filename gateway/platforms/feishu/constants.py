"""Constants, regex patterns, and tuning knobs for the Feishu platform adapter.

Extracted from ``gateway.platforms.feishu`` during modular refactoring so that
constants, types, and adapter logic can live in separate, focused modules.
"""

from __future__ import annotations

import re
from typing import Dict

from gateway.platforms.base import SUPPORTED_DOCUMENT_TYPES


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

_MARKDOWN_HINT_RE = re.compile(
    r"(^#{1,6}\s)|(^\s*[-*]\s)|(^\s*\d+\.\s)|(^\s*---+\s*$)|(```)|(`[^`\n]+`)|(\*\*[^*\n].+?\*\*)|(~~[^~\n].+?~~)|(<u>.+?</u>)|(\*[^*\n]+\*)|(\[[^\]]+\]\([^)]+\))|(^>\s)",
    re.MULTILINE,
)
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_MENTION_RE = re.compile(r"@_user_\d+")
_MULTISPACE_RE = re.compile(r"[ \t]{2,}")
_POST_CONTENT_INVALID_RE = re.compile(r"content format of the post type is incorrect", re.IGNORECASE)
_MARKDOWN_SPECIAL_CHARS_RE = re.compile(r"([\\`*_{}\[\]()#+\-!|>~])")
_MENTION_PLACEHOLDER_RE = re.compile(r"@_user_\d+")
_WHITESPACE_RE = re.compile(r"\s+")

# ---------------------------------------------------------------------------
# Media type sets and upload constants
# ---------------------------------------------------------------------------

_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
_AUDIO_EXTENSIONS = {".ogg", ".mp3", ".wav", ".m4a", ".aac", ".flac", ".opus", ".webm"}
_VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".3gp"}
_DOCUMENT_MIME_TO_EXT = {mime: ext for ext, mime in SUPPORTED_DOCUMENT_TYPES.items()}
_FEISHU_IMAGE_UPLOAD_TYPE = "message"
_FEISHU_FILE_UPLOAD_TYPE = "stream"
_FEISHU_OPUS_UPLOAD_EXTENSIONS = {".ogg", ".opus"}
_FEISHU_MEDIA_UPLOAD_EXTENSIONS = {".mp4", ".mov", ".avi", ".m4v"}
_FEISHU_DOC_UPLOAD_TYPES = {
    ".pdf": "pdf",
    ".doc": "doc",
    ".docx": "doc",
    ".xls": "xls",
    ".xlsx": "xls",
    ".ppt": "ppt",
    ".pptx": "ppt",
}

# ---------------------------------------------------------------------------
# Connection, retry and batching tuning
# ---------------------------------------------------------------------------

_MAX_TEXT_INJECT_BYTES = 100 * 1024
_FEISHU_CONNECT_ATTEMPTS = 3
_FEISHU_SEND_ATTEMPTS = 3
_FEISHU_APP_LOCK_SCOPE = "feishu-app-id"
_DEFAULT_TEXT_BATCH_DELAY_SECONDS = 0.6
_DEFAULT_TEXT_BATCH_MAX_MESSAGES = 8
_DEFAULT_TEXT_BATCH_MAX_CHARS = 4000
_DEFAULT_MEDIA_BATCH_DELAY_SECONDS = 0.8
_DEFAULT_DEDUP_CACHE_SIZE = 2048
_DEFAULT_WEBHOOK_HOST = "127.0.0.1"
_DEFAULT_WEBHOOK_PORT = 8765
_DEFAULT_WEBHOOK_PATH = "/feishu/webhook"

# ---------------------------------------------------------------------------
# TTL, rate-limit and webhook security constants
# ---------------------------------------------------------------------------

_FEISHU_DEDUP_TTL_SECONDS = 24 * 60 * 60          # 24 hours — matches openclaw
_FEISHU_SENDER_NAME_TTL_SECONDS = 10 * 60          # 10 minutes sender-name cache
_FEISHU_WEBHOOK_MAX_BODY_BYTES = 1 * 1024 * 1024   # 1 MB body limit
_FEISHU_WEBHOOK_RATE_WINDOW_SECONDS = 60            # sliding window for rate limiter
_FEISHU_WEBHOOK_RATE_LIMIT_MAX = 120               # max requests per window per IP — matches openclaw
_FEISHU_WEBHOOK_RATE_MAX_KEYS = 4096               # max tracked keys (prevents unbounded growth)
_FEISHU_WEBHOOK_BODY_TIMEOUT_SECONDS = 30          # max seconds to read request body
_FEISHU_WEBHOOK_ANOMALY_THRESHOLD = 25             # consecutive error responses before WARNING log
_FEISHU_WEBHOOK_ANOMALY_TTL_SECONDS = 6 * 60 * 60  # anomaly tracker TTL (6 hours) — matches openclaw
_FEISHU_CARD_ACTION_DEDUP_TTL_SECONDS = 15 * 60    # card action token dedup window (15 min)

_APPROVAL_CHOICE_MAP: Dict[str, str] = {
    "approve_once": "once",
    "approve_session": "session",
    "approve_always": "always",
    "deny": "deny",
}
_APPROVAL_LABEL_MAP: Dict[str, str] = {
    "once": "Approved once",
    "session": "Approved for session",
    "always": "Approved permanently",
    "deny": "Denied",
}
_FEISHU_BOT_MSG_TRACK_SIZE = 512                   # LRU size for tracking sent message IDs
_FEISHU_REPLY_FALLBACK_CODES = frozenset({230011, 231003})  # reply target withdrawn/missing → create fallback
_FEISHU_ACK_EMOJI = "OK"

# Cache size limits (prevent unbounded memory growth on long-running instances)
_FEISHU_SENDER_NAME_CACHE_MAX = 1024
_FEISHU_CHAT_INFO_CACHE_MAX = 512
_FEISHU_CHAT_INFO_TTL_SECONDS = 30 * 60            # 30 minutes
_FEISHU_MESSAGE_TEXT_CACHE_MAX = 1024
_FEISHU_WEBHOOK_ANOMALY_MAX_KEYS = 1024

# QR onboarding constants
_ONBOARD_ACCOUNTS_URLS = {
    "feishu": "https://accounts.feishu.cn",
    "lark": "https://accounts.larksuite.com",
}
_ONBOARD_OPEN_URLS = {
    "feishu": "https://open.feishu.cn",
    "lark": "https://open.larksuite.com",
}
_REGISTRATION_PATH = "/oauth/v1/app/registration"
_ONBOARD_REQUEST_TIMEOUT_S = 10

# ---------------------------------------------------------------------------
# Fallback display strings
# ---------------------------------------------------------------------------

FALLBACK_POST_TEXT = "[Rich text message]"
FALLBACK_FORWARD_TEXT = "[Merged forward message]"
FALLBACK_SHARE_CHAT_TEXT = "[Shared chat]"
FALLBACK_INTERACTIVE_TEXT = "[Interactive message]"
FALLBACK_IMAGE_TEXT = "[Image]"
FALLBACK_ATTACHMENT_TEXT = "[Attachment]"

# ---------------------------------------------------------------------------
# Post/card parsing helpers
# ---------------------------------------------------------------------------

_PREFERRED_LOCALES = ("zh_cn", "en_us")
_SUPPORTED_CARD_TEXT_KEYS = (
    "title",
    "text",
    "content",
    "label",
    "value",
    "name",
    "summary",
    "subtitle",
    "description",
    "placeholder",
    "hint",
)
_SKIP_TEXT_KEYS = {
    "tag",
    "type",
    "msg_type",
    "message_type",
    "chat_id",
    "open_chat_id",
    "share_chat_id",
    "file_key",
    "image_key",
    "user_id",
    "open_id",
    "union_id",
    "url",
    "href",
    "link",
    "token",
    "template",
    "locale",
}
