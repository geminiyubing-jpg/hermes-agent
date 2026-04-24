"""Feishu message parsing and normalization utilities."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Sequence

from .types import FeishuPostMediaRef, FeishuPostParseResult, FeishuNormalizedMessage, FeishuMentionRef, _FeishuBotIdentity
from .constants import (
    FALLBACK_POST_TEXT,
    FALLBACK_FORWARD_TEXT,
    FALLBACK_SHARE_CHAT_TEXT,
    FALLBACK_INTERACTIVE_TEXT,
    FALLBACK_IMAGE_TEXT,
    FALLBACK_ATTACHMENT_TEXT,
    _MARKDOWN_SPECIAL_CHARS_RE,
    _MARKDOWN_LINK_RE,
    _MENTION_PLACEHOLDER_RE,
    _MENTION_BOUNDARY_CHARS,
    _TRAILING_TERMINAL_PUNCT,
    _WHITESPACE_RE,
    _MULTISPACE_RE,
    _PREFERRED_LOCALES,
    _SUPPORTED_CARD_TEXT_KEYS,
    _SKIP_TEXT_KEYS,
)


# ---------------------------------------------------------------------------
# Markdown rendering helpers
# ---------------------------------------------------------------------------


def _escape_markdown_text(text: str) -> str:
    return _MARKDOWN_SPECIAL_CHARS_RE.sub(r"\\\1", text)


def _to_boolean(value: Any) -> bool:
    return value is True or value == 1 or value == "true"


def _is_style_enabled(style: Dict[str, Any] | None, key: str) -> bool:
    if not style:
        return False
    return _to_boolean(style.get(key))


def _wrap_inline_code(text: str) -> str:
    max_run = max([0, *[len(run) for run in re.findall(r"`+", text)]])
    fence = "`" * (max_run + 1)
    body = f" {text} " if text.startswith("`") or text.endswith("`") else text
    return f"{fence}{body}{fence}"


def _sanitize_fence_language(language: str) -> str:
    return language.strip().replace("\n", " ").replace("\r", " ")


def _render_text_element(element: Dict[str, Any]) -> str:
    text = str(element.get("text", "") or "")
    style = element.get("style")
    style_dict = style if isinstance(style, dict) else None

    if _is_style_enabled(style_dict, "code"):
        return _wrap_inline_code(text)

    rendered = _escape_markdown_text(text)
    if not rendered:
        return ""
    if _is_style_enabled(style_dict, "bold"):
        rendered = f"**{rendered}**"
    if _is_style_enabled(style_dict, "italic"):
        rendered = f"*{rendered}*"
    if _is_style_enabled(style_dict, "underline"):
        rendered = f"<u>{rendered}</u>"
    if _is_style_enabled(style_dict, "strikethrough"):
        rendered = f"~~{rendered}~~"
    return rendered


def _render_code_block_element(element: Dict[str, Any]) -> str:
    language = _sanitize_fence_language(
        str(element.get("language", "") or "") or str(element.get("lang", "") or "")
    )
    code = (
        str(element.get("text", "") or "") or str(element.get("content", "") or "")
    ).replace("\r\n", "\n")
    trailing_newline = "" if code.endswith("\n") else "\n"
    return f"```{language}\n{code}{trailing_newline}```"


def _strip_markdown_to_plain_text(text: str) -> str:
    """Strip markdown formatting to plain text for Feishu text fallbacks.

    Delegates common markdown stripping to the shared helper and adds
    Feishu-specific patterns (blockquotes, strikethrough, underline tags,
    horizontal rules, \\r\\n normalisation).
    """
    from gateway.platforms.helpers import strip_markdown
    plain = text.replace("\r\n", "\n")
    plain = _MARKDOWN_LINK_RE.sub(lambda m: f"{m.group(1)} ({m.group(2).strip()})", plain)
    plain = re.sub(r"^>\s?", "", plain, flags=re.MULTILINE)
    plain = re.sub(r"^\s*---+\s*$", "---", plain, flags=re.MULTILINE)
    plain = re.sub(r"~~([^~\n]+)~~", r"\1", plain)
    plain = re.sub(r"<u>([\s\S]*?)</u>", r"\1", plain)
    plain = strip_markdown(plain)
    return plain


def _coerce_int(value: Any, default: Optional[int] = None, min_value: int = 0) -> Optional[int]:
    """Coerce value to int with optional default and minimum constraint."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= min_value else default


def _coerce_required_int(value: Any, default: int, min_value: int = 0) -> int:
    parsed = _coerce_int(value, default=default, min_value=min_value)
    return default if parsed is None else parsed


# ---------------------------------------------------------------------------
# Post payload builders and parsers
# ---------------------------------------------------------------------------


def _build_markdown_post_payload(content: str) -> str:
    return json.dumps(
        {
            "zh_cn": {
                "content": [
                    [
                        {
                            "tag": "md",
                            "text": content,
                        }
                    ]
                ],
            }
        },
        ensure_ascii=False,
    )


def parse_feishu_post_payload(
    payload: Any,
    *,
    mentions_map: Optional[Dict[str, FeishuMentionRef]] = None,
) -> FeishuPostParseResult:
    resolved = _resolve_post_payload(payload)
    if not resolved:
        return FeishuPostParseResult(text_content=FALLBACK_POST_TEXT)

    image_keys: List[str] = []
    media_refs: List[FeishuPostMediaRef] = []
    parts: List[str] = []

    title = _normalize_feishu_text(str(resolved.get("title", "")).strip())
    if title:
        parts.append(title)

    for row in resolved.get("content", []) or []:
        if not isinstance(row, list):
            continue
        row_text = _normalize_feishu_text(
            "".join(
                _render_post_element(item, image_keys, media_refs, mentions_map)
                for item in row
            )
        )
        if row_text:
            parts.append(row_text)

    return FeishuPostParseResult(
        text_content="\n".join(parts).strip() or FALLBACK_POST_TEXT,
        image_keys=image_keys,
        media_refs=media_refs,
    )


def _resolve_post_payload(payload: Any) -> Dict[str, Any]:
    direct = _to_post_payload(payload)
    if direct:
        return direct
    if not isinstance(payload, dict):
        return {}

    wrapped = payload.get("post")
    wrapped_direct = _resolve_locale_payload(wrapped)
    if wrapped_direct:
        return wrapped_direct
    return _resolve_locale_payload(payload)


def _resolve_locale_payload(payload: Any) -> Dict[str, Any]:
    direct = _to_post_payload(payload)
    if direct:
        return direct
    if not isinstance(payload, dict):
        return {}

    for key in _PREFERRED_LOCALES:
        candidate = _to_post_payload(payload.get(key))
        if candidate:
            return candidate
    for value in payload.values():
        candidate = _to_post_payload(value)
        if candidate:
            return candidate
    return {}


def _to_post_payload(candidate: Any) -> Dict[str, Any]:
    if not isinstance(candidate, dict):
        return {}
    content = candidate.get("content")
    if not isinstance(content, list):
        return {}
    return {
        "title": str(candidate.get("title", "") or ""),
        "content": content,
    }


def _render_post_element(
    element: Any,
    image_keys: List[str],
    media_refs: List[FeishuPostMediaRef],
    mentions_map: Optional[Dict[str, FeishuMentionRef]] = None,
) -> str:
    if isinstance(element, str):
        return element
    if not isinstance(element, dict):
        return ""

    tag = str(element.get("tag", "")).strip().lower()
    if tag == "text":
        return _render_text_element(element)
    if tag == "a":
        href = str(element.get("href", "")).strip()
        label = str(element.get("text", href) or "").strip()
        if not label:
            return ""
        escaped_label = _escape_markdown_text(label)
        return f"[{escaped_label}]({href})" if href else escaped_label
    if tag == "at":
        # Post <at> user_id is a placeholder ("@_user_N" or "@_all"); look up
        # the real ref in mentions_map for the display name.
        placeholder = str(element.get("user_id", "")).strip()
        if placeholder == "@_all":
            # Feishu SDK sometimes omits @_all from the top-level mentions
            # payload; record it here so the caller's mention list stays complete.
            if mentions_map is not None and "@_all" not in mentions_map:
                mentions_map["@_all"] = FeishuMentionRef(is_all=True)
            return "@all"
        ref = (mentions_map or {}).get(placeholder)
        if ref is not None:
            display_name = ref.name or ref.open_id or "user"
        else:
            display_name = str(element.get("user_name", "")).strip() or "user"
        return f"@{_escape_markdown_text(display_name)}"
    if tag in {"img", "image"}:
        image_key = str(element.get("image_key", "")).strip()
        if image_key and image_key not in image_keys:
            image_keys.append(image_key)
        alt = str(element.get("text", "")).strip() or str(element.get("alt", "")).strip()
        return f"[Image: {alt}]" if alt else "[Image]"
    if tag in {"media", "file", "audio", "video"}:
        file_key = str(element.get("file_key", "")).strip()
        file_name = (
            str(element.get("file_name", "")).strip()
            or str(element.get("title", "")).strip()
            or str(element.get("text", "")).strip()
        )
        if file_key:
            media_refs.append(
                FeishuPostMediaRef(
                    file_key=file_key,
                    file_name=file_name,
                    resource_type=tag if tag in {"audio", "video"} else "file",
                )
            )
        return f"[Attachment: {file_name}]" if file_name else "[Attachment]"
    if tag in {"emotion", "emoji"}:
        label = str(element.get("text", "")).strip() or str(element.get("emoji_type", "")).strip()
        return f":{_escape_markdown_text(label)}:" if label else "[Emoji]"
    if tag == "br":
        return "\n"
    if tag in {"hr", "divider"}:
        return "\n\n---\n\n"
    if tag == "code":
        code = str(element.get("text", "") or "") or str(element.get("content", "") or "")
        return _wrap_inline_code(code) if code else ""
    if tag in {"code_block", "pre"}:
        return _render_code_block_element(element)

    nested_parts: List[str] = []
    for key in ("text", "title", "content", "children", "elements"):
        extracted = _render_nested_post(element.get(key), image_keys, media_refs, mentions_map)
        if extracted:
            nested_parts.append(extracted)
    return " ".join(part for part in nested_parts if part)


def _render_nested_post(
    value: Any,
    image_keys: List[str],
    media_refs: List[FeishuPostMediaRef],
    mentions_map: Optional[Dict[str, FeishuMentionRef]] = None,
) -> str:
    if isinstance(value, str):
        return _escape_markdown_text(value)
    if isinstance(value, list):
        return " ".join(
            part
            for item in value
            for part in [_render_nested_post(item, image_keys, media_refs, mentions_map)]
            if part
        )
    if isinstance(value, dict):
        direct = _render_post_element(value, image_keys, media_refs, mentions_map)
        if direct:
            return direct
        return " ".join(
            part
            for item in value.values()
            for part in [_render_nested_post(item, image_keys, media_refs, mentions_map)]
            if part
        )
    return ""


# ---------------------------------------------------------------------------
# Message normalization
# ---------------------------------------------------------------------------


def normalize_feishu_message(
    *,
    message_type: str,
    raw_content: str,
    mentions: Optional[Sequence[Any]] = None,
    bot: _FeishuBotIdentity = _FeishuBotIdentity(),
) -> FeishuNormalizedMessage:
    normalized_type = str(message_type or "").strip().lower()
    payload = _load_feishu_payload(raw_content)
    mentions_map = _build_mentions_map(mentions, bot)

    if normalized_type == "text":
        text = str(payload.get("text", "") or "")
        # Feishu SDK sometimes omits @_all from the mentions payload even when
        # the text literal contains it (confirmed via im.v1.message.get).
        if "@_all" in text and "@_all" not in mentions_map:
            mentions_map["@_all"] = FeishuMentionRef(is_all=True)
        return FeishuNormalizedMessage(
            raw_type=normalized_type,
            text_content=_normalize_feishu_text(text, mentions_map),
            mentions=list(mentions_map.values()),
        )
    if normalized_type == "post":
        # The walker writes back to mentions_map if it encounters
        # <at user_id="@_all">, so reading .values() after parsing is enough.
        parsed_post = parse_feishu_post_payload(payload, mentions_map=mentions_map)
        return FeishuNormalizedMessage(
            raw_type=normalized_type,
            text_content=parsed_post.text_content,
            image_keys=list(parsed_post.image_keys),
            media_refs=list(parsed_post.media_refs),
            mentions=list(mentions_map.values()),
            relation_kind="post",
        )
    mention_refs = list(mentions_map.values())
    if normalized_type == "image":
        image_key = str(payload.get("image_key", "") or "").strip()
        alt_text = _normalize_feishu_text(
            str(payload.get("text", "") or "")
            or str(payload.get("alt", "") or "")
            or FALLBACK_IMAGE_TEXT,
            mentions_map,
        )
        return FeishuNormalizedMessage(
            raw_type=normalized_type,
            text_content=alt_text if alt_text != FALLBACK_IMAGE_TEXT else "",
            preferred_message_type="photo",
            image_keys=[image_key] if image_key else [],
            relation_kind="image",
            mentions=mention_refs,
        )
    if normalized_type in {"file", "audio", "media"}:
        media_ref = _build_media_ref_from_payload(payload, resource_type=normalized_type)
        placeholder = _attachment_placeholder(media_ref.file_name)
        return FeishuNormalizedMessage(
            raw_type=normalized_type,
            text_content="",
            preferred_message_type="audio" if normalized_type == "audio" else "document",
            media_refs=[media_ref] if media_ref.file_key else [],
            relation_kind=normalized_type,
            metadata={"placeholder_text": placeholder},
            mentions=mention_refs,
        )
    if normalized_type == "merge_forward":
        return _normalize_merge_forward_message(payload)
    if normalized_type == "share_chat":
        return _normalize_share_chat_message(payload)
    if normalized_type in {"interactive", "card"}:
        return _normalize_interactive_message(normalized_type, payload)

    return FeishuNormalizedMessage(raw_type=normalized_type, text_content="")


def _load_feishu_payload(raw_content: str) -> Dict[str, Any]:
    try:
        parsed = json.loads(raw_content) if raw_content else {}
    except json.JSONDecodeError:
        return {"text": raw_content}
    return parsed if isinstance(parsed, dict) else {"content": parsed}


def _normalize_merge_forward_message(payload: Dict[str, Any]) -> FeishuNormalizedMessage:
    title = _first_non_empty_text(
        payload.get("title"),
        payload.get("summary"),
        payload.get("preview"),
        _find_first_text(payload, keys=("title", "summary", "preview", "description")),
    )
    entries = _collect_forward_entries(payload)
    lines: List[str] = []
    if title:
        lines.append(title)
    lines.extend(entries[:8])
    text_content = "\n".join(lines).strip() or FALLBACK_FORWARD_TEXT
    return FeishuNormalizedMessage(
        raw_type="merge_forward",
        text_content=text_content,
        relation_kind="merge_forward",
        metadata={"entry_count": len(entries), "title": title},
    )


def _normalize_share_chat_message(payload: Dict[str, Any]) -> FeishuNormalizedMessage:
    chat_name = _first_non_empty_text(
        payload.get("chat_name"),
        payload.get("name"),
        payload.get("title"),
        _find_first_text(payload, keys=("chat_name", "name", "title")),
    )
    share_id = _first_non_empty_text(
        payload.get("chat_id"),
        payload.get("open_chat_id"),
        payload.get("share_chat_id"),
    )
    lines = []
    if chat_name:
        lines.append(f"Shared chat: {chat_name}")
    else:
        lines.append(FALLBACK_SHARE_CHAT_TEXT)
    if share_id:
        lines.append(f"Chat ID: {share_id}")
    text_content = "\n".join(lines)
    return FeishuNormalizedMessage(
        raw_type="share_chat",
        text_content=text_content,
        relation_kind="share_chat",
        metadata={"chat_id": share_id, "chat_name": chat_name},
    )


def _normalize_interactive_message(message_type: str, payload: Dict[str, Any]) -> FeishuNormalizedMessage:
    card_payload = payload.get("card") if isinstance(payload.get("card"), dict) else payload
    title = _first_non_empty_text(
        _find_header_title(card_payload),
        payload.get("title"),
        _find_first_text(card_payload, keys=("title", "summary", "subtitle")),
    )
    body_lines = _collect_card_lines(card_payload)
    actions = _collect_action_labels(card_payload)

    lines: List[str] = []
    if title:
        lines.append(title)
    for line in body_lines:
        if line != title:
            lines.append(line)
    if actions:
        lines.append(f"Actions: {', '.join(actions)}")

    text_content = "\n".join(lines[:12]).strip() or FALLBACK_INTERACTIVE_TEXT
    return FeishuNormalizedMessage(
        raw_type=message_type,
        text_content=text_content,
        relation_kind="interactive",
        metadata={"title": title, "actions": actions},
    )


# ---------------------------------------------------------------------------
# Content extraction utilities (card / forward / text walking)
# ---------------------------------------------------------------------------


def _collect_forward_entries(payload: Dict[str, Any]) -> List[str]:
    candidates: List[Any] = []
    for key in ("messages", "items", "message_list", "records", "content"):
        value = payload.get(key)
        if isinstance(value, list):
            candidates.extend(value)
    entries: List[str] = []
    for item in candidates:
        if not isinstance(item, dict):
            text = _normalize_feishu_text(str(item or ""))
            if text:
                entries.append(f"- {text}")
            continue
        sender = _first_non_empty_text(
            item.get("sender_name"),
            item.get("user_name"),
            item.get("sender"),
            item.get("name"),
        )
        nested_type = str(item.get("message_type", "") or item.get("msg_type", "")).strip().lower()
        if nested_type == "post":
            body = parse_feishu_post_payload(item.get("content") or item).text_content
        else:
            body = _first_non_empty_text(
                item.get("text"),
                item.get("summary"),
                item.get("preview"),
                item.get("content"),
                _find_first_text(item, keys=("text", "content", "summary", "preview", "title")),
            )
        body = _normalize_feishu_text(body)
        if sender and body:
            entries.append(f"- {sender}: {body}")
        elif body:
            entries.append(f"- {body}")
    return _unique_lines(entries)


def _collect_card_lines(payload: Any) -> List[str]:
    lines = _collect_text_segments(payload, in_rich_block=False)
    normalized = [_normalize_feishu_text(line) for line in lines]
    return _unique_lines([line for line in normalized if line])


def _collect_action_labels(payload: Any) -> List[str]:
    labels: List[str] = []
    for item in _walk_nodes(payload):
        if not isinstance(item, dict):
            continue
        tag = str(item.get("tag", "") or item.get("type", "")).strip().lower()
        if tag not in {"button", "select_static", "overflow", "date_picker", "picker"}:
            continue
        label = _first_non_empty_text(
            item.get("text"),
            item.get("name"),
            item.get("value"),
            _find_first_text(item, keys=("text", "content", "name", "value")),
        )
        if label:
            labels.append(label)
    return _unique_lines(labels)


def _collect_text_segments(value: Any, *, in_rich_block: bool) -> List[str]:
    if isinstance(value, str):
        return [_normalize_feishu_text(value)] if in_rich_block else []
    if isinstance(value, list):
        segments: List[str] = []
        for item in value:
            segments.extend(_collect_text_segments(item, in_rich_block=in_rich_block))
        return segments
    if not isinstance(value, dict):
        return []

    tag = str(value.get("tag", "") or value.get("type", "")).strip().lower()
    next_in_rich_block = in_rich_block or tag in {
        "plain_text",
        "lark_md",
        "markdown",
        "note",
        "div",
        "column_set",
        "column",
        "action",
        "button",
        "select_static",
        "date_picker",
    }

    segments: List[str] = []
    for key in _SUPPORTED_CARD_TEXT_KEYS:
        item = value.get(key)
        if isinstance(item, str) and next_in_rich_block:
            normalized = _normalize_feishu_text(item)
            if normalized:
                segments.append(normalized)

    for key, item in value.items():
        if key in _SKIP_TEXT_KEYS:
            continue
        segments.extend(_collect_text_segments(item, in_rich_block=next_in_rich_block))
    return segments


def _build_media_ref_from_payload(payload: Dict[str, Any], *, resource_type: str) -> FeishuPostMediaRef:
    file_key = str(payload.get("file_key", "") or "").strip()
    file_name = _first_non_empty_text(
        payload.get("file_name"),
        payload.get("title"),
        payload.get("text"),
    )
    effective_type = resource_type if resource_type in {"audio", "video"} else "file"
    return FeishuPostMediaRef(file_key=file_key, file_name=file_name, resource_type=effective_type)


def _attachment_placeholder(file_name: str) -> str:
    normalized_name = _normalize_feishu_text(file_name)
    return f"[Attachment: {normalized_name}]" if normalized_name else FALLBACK_ATTACHMENT_TEXT


def _find_header_title(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    header = payload.get("header")
    if not isinstance(header, dict):
        return ""
    title = header.get("title")
    if isinstance(title, dict):
        return _first_non_empty_text(title.get("content"), title.get("text"), title.get("name"))
    return _normalize_feishu_text(str(title or ""))


def _find_first_text(payload: Any, *, keys: tuple[str, ...]) -> str:
    for node in _walk_nodes(payload):
        if not isinstance(node, dict):
            continue
        for key in keys:
            value = node.get(key)
            if isinstance(value, str):
                normalized = _normalize_feishu_text(value)
                if normalized:
                    return normalized
    return ""


def _walk_nodes(value: Any):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk_nodes(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_nodes(item)


def _first_non_empty_text(*values: Any) -> str:
    for value in values:
        if isinstance(value, str):
            normalized = _normalize_feishu_text(value)
            if normalized:
                return normalized
        elif value is not None and not isinstance(value, (dict, list)):
            normalized = _normalize_feishu_text(str(value))
            if normalized:
                return normalized
    return ""


# ---------------------------------------------------------------------------
# General text utilities
# ---------------------------------------------------------------------------


def _normalize_feishu_text(
    text: str,
    mentions_map: Optional[Dict[str, FeishuMentionRef]] = None,
) -> str:
    def _sub(match: "re.Match[str]") -> str:
        key = match.group(0)
        ref = (mentions_map or {}).get(key)
        if ref is None:
            return " "
        name = ref.name or ref.open_id or "user"
        return f"@{name}"

    cleaned = _MENTION_PLACEHOLDER_RE.sub(_sub, text or "")
    cleaned = cleaned.replace("@_all", "@all")
    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = "\n".join(_WHITESPACE_RE.sub(" ", line).strip() for line in cleaned.split("\n"))
    cleaned = "\n".join(line for line in cleaned.split("\n") if line)
    cleaned = _MULTISPACE_RE.sub(" ", cleaned)
    return cleaned.strip()


def _unique_lines(lines: List[str]) -> List[str]:
    seen: set[str] = set()
    unique: List[str] = []
    for line in lines:
        if not line or line in seen:
            continue
        seen.add(line)
        unique.append(line)
    return unique


# ---------------------------------------------------------------------------
# Mention helpers
# ---------------------------------------------------------------------------


def _extract_mention_ids(mention: Any) -> tuple[str, str]:
    # Returns (open_id, user_id). im.v1.message.get hands back id as a string
    # plus id_type discriminator; event payloads hand back a nested UserId
    # object carrying both fields.
    mention_id = getattr(mention, "id", None)
    if isinstance(mention_id, str):
        id_type = str(getattr(mention, "id_type", "") or "").lower()
        if id_type == "open_id":
            return mention_id, ""
        if id_type == "user_id":
            return "", mention_id
        return "", ""
    if mention_id is None:
        return "", ""
    return (
        str(getattr(mention_id, "open_id", "") or ""),
        str(getattr(mention_id, "user_id", "") or ""),
    )


def _build_mentions_map(
    mentions: Optional[Sequence[Any]],
    bot: _FeishuBotIdentity,
) -> Dict[str, FeishuMentionRef]:
    result: Dict[str, FeishuMentionRef] = {}
    for mention in mentions or []:
        key = str(getattr(mention, "key", "") or "")
        if not key:
            continue
        if key == "@_all":
            result[key] = FeishuMentionRef(is_all=True)
            continue
        open_id, user_id = _extract_mention_ids(mention)
        name = str(getattr(mention, "name", "") or "").strip()
        result[key] = FeishuMentionRef(
            name=name,
            open_id=open_id,
            is_self=bot.matches(open_id=open_id, user_id=user_id, name=name),
        )
    return result


def _build_mention_hint(mentions: Sequence[FeishuMentionRef]) -> str:
    parts: List[str] = []
    seen: set = set()
    for ref in mentions:
        if ref.is_self:
            continue
        signature = (ref.is_all, ref.open_id, ref.name)
        if signature in seen:
            continue
        seen.add(signature)
        if ref.is_all:
            parts.append("@all")
        elif ref.open_id:
            parts.append(f"{ref.name or 'unknown'} (open_id={ref.open_id})")
        else:
            parts.append(ref.name or "unknown")
    return f"[Mentioned: {', '.join(parts)}]" if parts else ""


def _strip_edge_self_mentions(
    text: str,
    mentions: Sequence[FeishuMentionRef],
) -> str:
    # Leading: strip consecutive self-mentions unconditionally.
    # Trailing: strip only when followed by whitespace/terminal punct, so
    # mid-sentence references ("don't @Bot again") stay intact.
    # Leading word-boundary prevents @Al from eating @Alice.
    if not text:
        return text
    self_names = [
        f"@{ref.name or ref.open_id or 'user'}"
        for ref in mentions
        if ref.is_self
    ]
    if not self_names:
        return text

    remaining = text.lstrip()
    while True:
        for nm in self_names:
            if not remaining.startswith(nm):
                continue
            after = remaining[len(nm):]
            if after and after[0] not in _MENTION_BOUNDARY_CHARS:
                continue
            remaining = after.lstrip()
            break
        else:
            break

    while True:
        i = len(remaining)
        while i > 0 and remaining[i - 1] in _TRAILING_TERMINAL_PUNCT:
            i -= 1
        body = remaining[:i]
        tail = remaining[i:]
        for nm in self_names:
            if body.endswith(nm):
                remaining = body[: -len(nm)].rstrip() + tail
                break
        else:
            return remaining
