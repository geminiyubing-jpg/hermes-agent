"""Feishu platform adapter – modular sub-package.

All public (and test-used private) symbols are re-exported here so that
existing imports continue to work:
    from gateway.platforms.feishu import FeishuAdapter
    from gateway.platforms.feishu import normalize_feishu_message

NOTE: Many private symbols (prefixed with ``_``) and stdlib modules are
re-exported solely for backward-compatibility with existing test suites
that ``patch()`` them via the package path.  New tests should import
from the specific submodule directly, e.g.:
    from gateway.platforms.feishu.onboarding import _post_registration
"""

# ── Public API ──────────────────────────────────────────────────────────
from gateway.platforms.feishu.adapter import (  # noqa: F401
    FeishuAdapter,
    check_feishu_requirements,
    FEISHU_AVAILABLE,
    FEISHU_WEBSOCKET_AVAILABLE,
    FEISHU_WEBHOOK_AVAILABLE,
    FEISHU_DOMAIN,
    LARK_DOMAIN,
)

# ── Test-only re-exports (backward compat) ──────────────────────────────
# Tests should migrate to importing from the specific submodule.
from gateway.platforms.feishu.adapter import (  # noqa: F401
    EventDispatcherHandler,
    FeishuWSClient,
    lark,
    web,
    asyncio,
    threading,
    cache_image_from_url,
    acquire_scoped_lock,
    release_scoped_lock,
    time,
    urlopen,
    CallBackCard,
    P2CardActionTriggerResponse,
    _FEISHU_DEDUP_TTL_SECONDS,
)

from gateway.platforms.feishu.onboarding import (  # noqa: F401
    probe_bot,
    qr_register,
    _post_registration,
    _init_registration,
    _begin_registration,
    _poll_registration,
    _render_qr,
    _probe_bot_sdk,
    _qrcode_mod,
)

# ── Data types ──────────────────────────────────────────────────────────
from gateway.platforms.feishu.types import (  # noqa: F401
    FeishuPostMediaRef,
    FeishuPostParseResult,
    FeishuNormalizedMessage,
    FeishuAdapterSettings,
    FeishuGroupRule,
    FeishuBatchState,
)

# ── Message parsing ────────────────────────────────────────────────────
from gateway.platforms.feishu.message_parser import (  # noqa: F401
    normalize_feishu_message,
    parse_feishu_post_payload,
)

# ── Constants (test-used) ──────────────────────────────────────────────
from gateway.platforms.feishu.constants import (  # noqa: F401
    _FEISHU_WEBHOOK_RATE_LIMIT_MAX,
    _FEISHU_WEBHOOK_RATE_WINDOW_SECONDS,
    _FEISHU_WEBHOOK_MAX_BODY_BYTES,
)

# ── WebSocket helper (test-used) ───────────────────────────────────────
from gateway.platforms.feishu.websocket import (  # noqa: F401
    _run_official_feishu_ws_client,
)
