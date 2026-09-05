"""
Self Evolution Plugin — Lifecycle Hooks
========================================

Registered hooks:

  - post_tool_call:  Collect per-tool telemetry
  - on_session_end:  Compute quality score + detect outcome signals
  - pre_llm_call:    Inject learned strategy hints
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ── Correction detection patterns (inspired by Claude Code conversation-analyzer) ──

CORRECTION_PATTERNS = re.compile(
    r"(不对|错误|重试|不要|停|stop|wrong|retry|no|don't|not that|不是|不是这个|为什么|换一种)",
    re.IGNORECASE,
)

FRUSTRATION_PATTERNS = re.compile(
    r"(烦|慢|太慢|浪费时间|why did you|无语|算了|够了)",
    re.IGNORECASE,
)


# ── post_tool_call ───────────────────────────────────────────────────────

def on_tool_call(**kwargs) -> None:
    """Collect per-tool invocation telemetry."""
    from self_evolution.db import insert

    tool_name = kwargs.get("tool_name", "unknown")
    started_at = kwargs.get("started_at", time.time())
    duration_ms = kwargs.get("duration_ms", 0)
    success = kwargs.get("success", True)
    error_type = kwargs.get("error_type") if not success else None
    session_id = kwargs.get("session_id", "")
    turn_number = kwargs.get("turn_number", 0)

    try:
        insert("tool_invocations", {
            "session_id": session_id,
            "tool_name": tool_name,
            "duration_ms": duration_ms,
            "success": success,
            "error_type": error_type,
            "turn_number": turn_number,
            "created_at": started_at,
        })
    except Exception as exc:
        logger.warning("telemetry insert failed: %s", exc)

    # Update terminal circuit breaker state
    if tool_name == "terminal":
        _update_breaker_on_result(session_id, success)


# ── on_session_end ───────────────────────────────────────────────────────

def on_session_end(**kwargs) -> None:
    """Compute quality score and detect outcome signals when session ends."""
    from self_evolution.db import insert, insert_many
    from self_evolution.quality_scorer import compute_score

    # Support both nested session_data (gateway) and flat kwargs (CLI/run_agent)
    session_data = kwargs.get("session_data")
    if not isinstance(session_data, dict):
        session_data = kwargs

    session_id = session_data.get("session_id", "")

    if not session_id:
        return

    # Compute quality score
    score = compute_score(session_data)
    try:
        insert("session_scores", score.to_db_row())
    except Exception as exc:
        logger.warning("score insert failed: %s", exc)

    # Detect and batch-insert outcome signals
    signals = _detect_outcome_signals(session_data, kwargs)
    if signals:
        try:
            insert_many("outcome_signals", signals)
        except Exception as exc:
            logger.warning("signal insert failed: %s", exc)


def _detect_outcome_signals(session_data: dict, kwargs: dict) -> list:
    """Detect implicit outcome signals from session behavior.

    Inspired by Claude Code conversation-analyzer's signal detection:
    - Explicit corrections: user says "不对", "重试"
    - Frustration signals: user says "为什么", "太慢"
    - Completion / interruption status
    - Budget exhaustion
    """
    signals = []
    session_id = session_data.get("session_id", "")

    # Completion signal
    completed = session_data.get("completed", False)
    interrupted = session_data.get("interrupted", False)
    partial = session_data.get("partial", False)

    if completed:
        signals.append({
            "session_id": session_id,
            "signal_type": "completed",
            "signal_value": 1.0,
            "metadata": "{}",
        })
    elif interrupted:
        signals.append({
            "session_id": session_id,
            "signal_type": "interrupted",
            "signal_value": 0.5,
            "metadata": "{}",
        })
    elif partial:
        signals.append({
            "session_id": session_id,
            "signal_type": "partial",
            "signal_value": 0.3,
            "metadata": "{}",
        })

    # Budget exhaustion
    max_iterations = session_data.get("max_iterations", 0)
    iterations = session_data.get("iterations", 0)
    if max_iterations and iterations >= max_iterations:
        signals.append({
            "session_id": session_id,
            "signal_type": "budget_exhausted",
            "signal_value": 0.0,
            "metadata": f'{{"iterations": {iterations}}}',
        })

    # User correction / frustration detection from messages
    messages = session_data.get("messages", [])
    for msg in messages:
        if msg.get("role") != "user":
            continue
        content = msg.get("content", "")
        if isinstance(content, list):
            content = " ".join(
                block.get("text", "") for block in content
                if isinstance(block, dict) and block.get("type") == "text"
            )

        if CORRECTION_PATTERNS.search(content):
            signals.append({
                "session_id": session_id,
                "signal_type": "correction",
                "signal_value": 0.2,
                "metadata": json.dumps({"text": content[:100]}, ensure_ascii=False),
            })
            break  # Only one correction signal per session

        if FRUSTRATION_PATTERNS.search(content):
            signals.append({
                "session_id": session_id,
                "signal_type": "frustration",
                "signal_value": 0.1,
                "metadata": json.dumps({"text": content[:100]}, ensure_ascii=False),
            })
            break

    return signals


# ── pre_llm_call ─────────────────────────────────────────────────────────

def on_pre_llm_call(**kwargs) -> Optional[Dict[str, Any]]:
    """Inject learned strategy hints into system prompt.

    Inspired by Claude Code learning-output-style SessionStart hook pattern:
    automatically inject behavioral context without user action.
    """
    from self_evolution.strategy_injector import inject_hints

    try:
        hints = inject_hints(kwargs)
        if hints:
            return {"system_hint": hints}
    except Exception as exc:
        logger.warning("strategy injection failed: %s", exc)

    return None


# ── Terminal Pre-flight Checks (circuit breaker + path validation) ──────

# Circuit breaker state (same pattern as mcp_tool.py)
_terminal_error_counts: Dict[str, int] = {}
_terminal_breaker_opened_at: Dict[str, float] = {}
_CB_THRESHOLD = 3
_CB_COOLDOWN_SEC = 60.0

# Path extraction patterns for common commands
_PATH_ARG_RE = re.compile(
    r"""(?:^|\s)
        (?:cd|ls|cat|head|tail|cp|mv|rm|chmod|mkdir|touch|python\d?|node|pip\d?\s+install\s+-r|source|\.\/|\.\.\/|\/)
        \s+
        (?P<path>[^\s;&|>]+)
    """,
    re.VERBOSE,
)

# Skip path validation for these command prefixes
_SKIP_PATH_CHECK = re.compile(
    r"^\s*(?:pip\d?\s+install|npm\s+install|apt|brew|yum|dnf|echo|printf|export|set|unset|alias|unalias)",
    re.IGNORECASE,
)


def _circuit_breaker_check(session_id: str) -> Optional[str]:
    """Return block message if circuit breaker is open for this session."""
    count = _terminal_error_counts.get(session_id, 0)
    if count < _CB_THRESHOLD:
        return None

    opened_at = _terminal_breaker_opened_at.get(session_id, 0)
    elapsed = time.monotonic() - opened_at

    if elapsed < _CB_COOLDOWN_SEC:
        remaining = int(_CB_COOLDOWN_SEC - elapsed)
        return (
            f"Terminal circuit breaker active: {count} consecutive failures. "
            f"Retry in ~{remaining}s. Consider simplifying the command."
        )

    # Half-open: allow one probe attempt
    return None


def _update_breaker_on_result(session_id: str, success: bool) -> None:
    """Update circuit breaker state based on tool result."""
    if success:
        _terminal_error_counts[session_id] = 0
        _terminal_breaker_opened_at.pop(session_id, None)
    else:
        count = _terminal_error_counts.get(session_id, 0) + 1
        _terminal_error_counts[session_id] = count
        if count >= _CB_THRESHOLD:
            _terminal_breaker_opened_at[session_id] = time.monotonic()


def _validate_paths_in_command(command: str) -> Optional[str]:
    """Check if file/dir paths in the command exist. Return warning or None."""
    if not command or _SKIP_PATH_CHECK.match(command):
        return None

    # Don't check compound commands with && or || — too many false positives
    if "&&" in command or "||" in command or ";" in command:
        return None

    missing = []
    for m in _PATH_ARG_RE.finditer(command):
        path = m.group("path")
        # Skip flags, URLs, packages, wildcards
        if path.startswith("-") or path.startswith("http") or "*" in path:
            continue
        # Skip bare command names (no slash and no dot)
        if "/" not in path and "." not in path:
            continue
        if not os.path.exists(path):
            missing.append(path)

    if missing:
        paths_str = ", ".join(missing[:3])
        return f"Path pre-check: path(s) not found: {paths_str}. Verify the path exists before running."
    return None


# ── pre_tool_call ────────────────────────────────────────────────────────

def on_pre_tool_call(**kwargs) -> Optional[Dict[str, Any]]:
    """Terminal tool pre-flight checks via plugin hook.

    Provides:
      1. Circuit breaker — blocks after 3 consecutive terminal failures
      2. Path validation — warns if command references non-existent paths
    """
    tool_name = kwargs.get("tool_name", "")
    if tool_name != "terminal":
        return None

    args = kwargs.get("args", {})
    if not isinstance(args, dict):
        return None

    command = args.get("command", "")
    session_id = kwargs.get("session_id", "")

    # 1. Circuit breaker check
    msg = _circuit_breaker_check(session_id)
    if msg:
        return {"action": "block", "message": msg}

    # 2. Path existence pre-check
    msg = _validate_paths_in_command(command)
    if msg:
        return {"action": "block", "message": msg}

    return None


# ── Registration ─────────────────────────────────────────────────────────

def register_all(ctx) -> None:
    """Register all lifecycle hooks via PluginContext."""
    ctx.register_hook("post_tool_call", on_tool_call)
    ctx.register_hook("on_session_end", on_session_end)
    ctx.register_hook("pre_llm_call", on_pre_llm_call)
    ctx.register_hook("pre_tool_call", on_pre_tool_call)
