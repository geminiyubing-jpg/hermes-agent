"""
Self Evolution Plugin — Dream Engine (Reflection Engine)
=========================================================

Runs nightly at 1:00 to analyze the previous day's sessions.

Design reference: Claude Code plugins/hookify/agents/conversation-analyzer.md
  - Analyzes conversations in reverse chronological order
  - Detects: corrections, frustrations, repeated issues, reversions
  - Extracts tool usage patterns, converts to actionable rules
  - Categorizes by severity

We extend this pattern with:
  - Full automated analysis (not just on user request)
  - Error analysis (tool failures, retries, API errors)
  - Time waste analysis (slow tools, repeated ops, inefficient sessions)
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from self_evolution import db
from self_evolution.models import (
    ErrorAnalysis, ToolFailure, RetryPattern,
    WasteAnalysis, ToolDuration, RepeatedOperation,
    ReflectionReport,
)

logger = logging.getLogger(__name__)

# ── Model Configuration ──────────────────────────────────────────────────


def _load_model_config() -> dict:
    """Load model config from main hermes config.yaml (~/.hermes/config.yaml).

    Reads the primary model and first fallback provider to use for reflection,
    so the plugin always stays in sync with the user's model preferences.
    """
    try:
        from hermes_cli.config import load_config
        config = load_config()

        model_cfg = config.get("model", {})
        provider = model_cfg.get("provider", "")
        model_name = model_cfg.get("default", "")
        base_url = model_cfg.get("base_url", "")

        primary = {"provider": provider, "model": model_name}
        if base_url:
            primary["base_url"] = base_url

        # First fallback provider
        fallback = None
        fallbacks = config.get("fallback_providers", [])
        if fallbacks:
            fb = fallbacks[0]
            fallback = {
                "provider": fb.get("provider", ""),
                "model": fb.get("model", ""),
            }
            if fb.get("base_url"):
                fallback["base_url"] = fb["base_url"]

        return {"primary": primary, "fallback": fallback}

    except Exception:
        logger.debug("Failed to load hermes config, using defaults")
        return {
            "primary": {"provider": "zhipu", "model": "glm-5.1"},
            "fallback": None,
        }


class DreamEngine:
    """Nightly dream consolidation engine.

    Analyzes the previous day's sessions to find:
    1. Error patterns (tool failures, retries, incomplete tasks)
    2. Time waste patterns (slow tools, repeated operations, inefficient flows)
    3. Success patterns (what worked well)
    4. Generates actionable evolution proposals
    """

    def __init__(self, config: dict = None):
        self.config = config or _load_model_config()
        self._model_client = None
        self._current_prompt = ""

    def run(self, hours: int = 24) -> Optional[ReflectionReport]:
        """Main dream consolidation flow."""
        logger.info("Dream engine starting — analyzing last %d hours", hours)

        now = time.time()
        cutoff = now - (hours * 3600)

        try:
            # 1. Load session data
            scores = db.fetch_all(
                "session_scores",
                where="created_at >= ?",
                params=(cutoff,),
                order_by="created_at DESC",
            )
            tool_invocations = db.fetch_all(
                "tool_invocations",
                where="created_at >= ?",
                params=(cutoff,),
                order_by="created_at DESC",
            )
            signals = db.fetch_all(
                "outcome_signals",
                where="created_at >= ?",
                params=(cutoff,),
            )

            if not scores:
                logger.info("No sessions to analyze")
                return None

            # 2. Error analysis
            error_analysis = self._analyze_errors(scores, tool_invocations, signals)
            logger.info("Error analysis: %s", error_analysis.summary())

            # 3. Time waste analysis
            waste_analysis = self._analyze_time_waste(scores, tool_invocations)
            logger.info("Waste analysis: %s", waste_analysis.summary())

            # 4. Compute average score
            avg_score = (
                sum(s.get("composite_score", 0) for s in scores) / len(scores)
                if scores else 0
            )

            # 5. Build reflection prompt
            prompt = self._build_reflection_prompt(
                scores, tool_invocations, signals,
                error_analysis, waste_analysis, avg_score,
            )

            # 6. Call model for deep reflection
            reflection_text = self._call_model(prompt)
            if not reflection_text:
                logger.warning("Model returned empty reflection")
                return None

            # 7. Parse reflection report
            report = self._parse_reflection(
                reflection_text=reflection_text,
                period_start=cutoff,
                period_end=now,
                sessions_analyzed=len(scores),
                avg_score=avg_score,
                error_analysis=error_analysis,
                waste_analysis=waste_analysis,
            )

            # 8. Store report
            report_id = db.insert("reflection_reports", report.to_db_row())
            logger.info("Reflection report saved: id=%d, avg_score=%.3f", report_id, avg_score)

            # 9. Generate evolution proposals
            from self_evolution.evolution_proposer import generate_proposals
            proposals = generate_proposals(report, report_id)
            for p in proposals:
                db.insert("evolution_proposals", p.to_db_row())
            logger.info("Generated %d evolution proposals", len(proposals))

            # 10. Cleanup old data
            db.cleanup(days=30)

            return report

        except Exception as exc:
            logger.exception("Dream engine failed: %s", exc)
            return None

    # ── Error Analysis ────────────────────────────────────────────────────

    def _analyze_errors(
        self,
        scores: List[dict],
        invocations: List[dict],
        signals: List[dict],
    ) -> ErrorAnalysis:
        """Analyze all errors in the period.

        Inspired by Claude Code conversation-analyzer's signal detection.
        """
        # Tool failures
        failures = {}
        for inv in invocations:
            if not inv.get("success", True):
                tool = inv.get("tool_name", "unknown")
                error_type = inv.get("error_type", "unknown")
                key = f"{tool}:{error_type}"
                if key not in failures:
                    failures[key] = ToolFailure(
                        tool_name=tool,
                        error_type=error_type,
                        count=0,
                        sessions_affected=[],
                        example_session=inv.get("session_id", ""),
                    )
                failures[key].count += 1
                sid = inv.get("session_id", "")
                if sid and sid not in failures[key].sessions_affected:
                    failures[key].sessions_affected.append(sid)

        # Retry patterns (same tool called > 2 times in same session)
        retries = self._detect_retry_patterns(invocations)

        # Incomplete sessions
        incomplete = [
            s.get("session_id", "") for s in scores
            if s.get("completion_rate", 1.0) < 0.5
        ]

        # User corrections from signals
        corrections = [s for s in signals if s.get("signal_type") == "correction"]
        frustration = [s for s in signals if s.get("signal_type") == "frustration"]
        api_errors = [s for s in signals if s.get("signal_type") == "api_error"]

        # API error type distribution
        api_error_types: Dict[str, int] = {}
        for s in api_errors:
            meta = json.loads(s.get("metadata", "{}"))
            etype = meta.get("error_type", "unknown")
            api_error_types[etype] = api_error_types.get(etype, 0) + 1

        return ErrorAnalysis(
            tool_failures=sorted(failures.values(), key=lambda x: x.count, reverse=True),
            retry_patterns=retries,
            incomplete_sessions=incomplete,
            user_corrections=len(corrections),
            correction_examples=[s.get("metadata", "") for s in corrections[:3]],
            api_error_count=len(api_errors),
            api_error_types=api_error_types,
        )

    def _detect_retry_patterns(self, invocations: List[dict]) -> List[RetryPattern]:
        """Detect tools called > 2 times in same session."""
        session_tools: Dict[str, Dict[str, int]] = {}
        for inv in invocations:
            sid = inv.get("session_id", "")
            tool = inv.get("tool_name", "")
            if sid not in session_tools:
                session_tools[sid] = {}
            session_tools[sid][tool] = session_tools[sid].get(tool, 0) + 1

        patterns = []
        for sid, tools in session_tools.items():
            for tool, count in tools.items():
                if count > 2:
                    patterns.append(RetryPattern(
                        session_id=sid,
                        tool_name=tool,
                        attempt_count=count,
                        final_outcome="unknown",
                    ))
        return sorted(patterns, key=lambda x: x.attempt_count, reverse=True)[:20]

    # ── Time Waste Analysis ───────────────────────────────────────────────

    def _analyze_time_waste(
        self,
        scores: List[dict],
        invocations: List[dict],
    ) -> WasteAnalysis:
        """Analyze time waste patterns."""
        # Slowest tools
        tool_durations: Dict[str, List[int]] = {}
        for inv in invocations:
            tool = inv.get("tool_name", "")
            duration = inv.get("duration_ms", 0)
            if not duration:
                continue
            if tool not in tool_durations:
                tool_durations[tool] = []
            tool_durations[tool].append(duration)

        slowest = [
            ToolDuration(
                tool_name=tool,
                total_duration_ms=sum(durs),
                call_count=len(durs),
                avg_duration_ms=sum(durs) / len(durs),
            )
            for tool, durs in tool_durations.items()
        ]
        slowest.sort(key=lambda x: x.avg_duration_ms, reverse=True)

        # Repeated operations (same tool + same session > 3 times)
        session_tool_calls: Dict[str, Dict[str, int]] = {}
        for inv in invocations:
            sid = inv.get("session_id", "")
            tool = inv.get("tool_name", "")
            if sid not in session_tool_calls:
                session_tool_calls[sid] = {}
            session_tool_calls[sid][tool] = session_tool_calls[sid].get(tool, 0) + 1

        repeated = []
        for sid, tools in session_tool_calls.items():
            for tool, count in tools.items():
                if count > 3:
                    repeated.append(RepeatedOperation(
                        description=f"{tool} called {count} times",
                        count=count,
                        sessions=[sid],
                        wasted_ms=tool_durations.get(tool, [0])[0] * (count - 2) if tool in tool_durations else 0,
                    ))

        # Inefficient sessions (low efficiency score)
        inefficient = [
            s.get("session_id", "") for s in scores
            if s.get("efficiency_score", 1.0) < 0.3
        ]

        return WasteAnalysis(
            slowest_tools=slowest[:10],
            repeated_operations=sorted(repeated, key=lambda x: x.count, reverse=True)[:10],
            inefficient_sessions=inefficient,
            shortcut_opportunities=[],
        )

    # ── Reflection Prompt ─────────────────────────────────────────────────

    def _build_reflection_prompt(
        self,
        scores: List[dict],
        invocations: List[dict],
        signals: List[dict],
        errors: ErrorAnalysis,
        waste: WasteAnalysis,
        avg_score: float,
    ) -> str:
        """Build the reflection prompt for the model."""
        # Load prompt template
        template_path = Path(__file__).parent / "prompts" / "reflection.md"
        if template_path.exists():
            template = template_path.read_text(encoding="utf-8")
        else:
            template = _DEFAULT_REFLECTION_PROMPT

        # Compute statistics
        total_invocations = len(invocations)
        success_rate = (
            sum(1 for i in invocations if i.get("success", True)) / total_invocations * 100
            if total_invocations else 100
        )

        # Signal distribution
        signal_types = {}
        for s in signals:
            stype = s.get("signal_type", "unknown")
            signal_types[stype] = signal_types.get(stype, 0) + 1

        prompt = template.replace("{sessions_count}", str(len(scores)))
        prompt = prompt.replace("{avg_score}", f"{avg_score:.3f}")
        prompt = prompt.replace("{total_invocations}", str(total_invocations))
        prompt = prompt.replace("{success_rate}", f"{success_rate:.1f}")
        prompt = prompt.replace("{error_summary}", errors.summary())
        prompt = prompt.replace("{waste_summary}", waste.summary())
        prompt = prompt.replace("{signal_distribution}", json.dumps(signal_types, ensure_ascii=False))

        # Tool usage breakdown
        tool_counts: Dict[str, int] = {}
        for inv in invocations:
            tool = inv.get("tool_name", "")
            tool_counts[tool] = tool_counts.get(tool, 0) + 1
        prompt = prompt.replace("{tool_usage}", json.dumps(tool_counts, ensure_ascii=False, indent=2))

        return prompt

    # ── Model Call ────────────────────────────────────────────────────────

    def _call_model(self, prompt: str) -> Optional[str]:
        """Call the configured model (primary from hermes config, fallback if available)."""
        self._current_prompt = prompt

        # Try primary model first
        result = self._try_model_call(self.config["primary"])
        if result is not None:
            return result

        # Try fallback model
        fallback = self.config.get("fallback")
        if fallback:
            logger.warning("Primary model failed, trying fallback: %s", fallback.get("model"))
            return self._try_model_call(fallback)

        logger.warning("Primary model failed, no fallback configured")
        return None

    def _try_model_call(self, model_config: dict) -> Optional[str]:
        """Try to call a specific model.

        Resolves the provider and base_url from hermes config automatically.
        All providers use the OpenAI-compatible /chat/completions interface.
        """
        provider = model_config.get("provider", "")
        model = model_config.get("model", "")
        base_url = model_config.get("base_url", "")

        # Resolve base_url from hermes providers config if not explicit
        if not base_url:
            base_url = self._resolve_base_url(provider)

        # Resolve API key
        api_key = self._resolve_api_key(provider)

        if not base_url or not model:
            logger.warning("Incomplete model config: provider=%s model=%s", provider, model)
            return None

        return self._call_chat_completions(base_url, api_key, model)

    def _resolve_base_url(self, provider: str) -> str:
        """Resolve base_url from hermes provider config."""
        try:
            from hermes_cli.config import load_config
            config = load_config()

            # 1. Check custom_providers list (e.g. "custom-127-0-0-1-8000")
            for cp in config.get("custom_providers", []):
                name = cp.get("name", "")
                slug = "custom:" + name.strip().lower().replace(" ", "-")
                if provider in (name, slug):
                    return cp.get("base_url", cp.get("api", ""))

            # 2. Check providers dict
            providers = config.get("providers", {})
            if provider in providers:
                p = providers[provider]
                return p.get("api", p.get("base_url", ""))

            # 3. Known provider defaults
            known = {
                "zai": "https://open.bigmodel.cn/api/paas/v4",
                "zhipu": "https://open.bigmodel.cn/api/paas/v4",
                "openrouter": "https://openrouter.ai/api/v1",
            }
            return known.get(provider, "")
        except Exception:
            return ""

    def _resolve_api_key(self, provider: str) -> str:
        """Resolve API key for a provider from hermes config or env vars."""
        try:
            from hermes_cli.config import load_config
            config = load_config()

            # 1. Check custom_providers list
            for cp in config.get("custom_providers", []):
                name = cp.get("name", "")
                slug = "custom:" + name.strip().lower().replace(" ", "-")
                if provider in (name, slug):
                    key = cp.get("api_key", "")
                    if key:
                        return key
                    key_env = cp.get("key_env", "")
                    if key_env:
                        return os.getenv(key_env, "")

            # 2. Check providers config for key_env
            providers = config.get("providers", {})
            p = providers.get(provider, {})
            key_env = p.get("key_env", "")
            if key_env:
                return os.getenv(key_env, "")

            # 3. Check model-level api_key
            model_cfg = config.get("model", {})
            if model_cfg.get("api_key"):
                return model_cfg["api_key"]
        except Exception:
            pass

        # 4. Fallback env vars by provider
        env_map = {
            "zai": "ZAI_API_KEY",
            "zhipu": "ZHIPU_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
        }
        env_var = env_map.get(provider, "OPENAI_API_KEY")
        return os.getenv(env_var, "")

    def _call_chat_completions(
        self, base_url: str, api_key: str, model: str,
    ) -> Optional[str]:
        """Call OpenAI-compatible /chat/completions endpoint."""
        try:
            import requests
            url = f"{base_url.rstrip('/')}/chat/completions"
            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            resp = requests.post(
                url,
                headers=headers,
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "你是一个专业的AI agent性能分析专家。"},
                        {"role": "user", "content": self._current_prompt or ""},
                    ],
                    "temperature": 0.3,
                },
                timeout=300,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("choices", [{}])[0].get("message", {}).get("content", "")
            else:
                logger.debug("Model call failed: %d %s", resp.status_code, resp.text[:200])
        except Exception as exc:
            logger.debug("Chat completions call failed: %s", exc)
        return None

    # ── Reflection Parsing ────────────────────────────────────────────────

    def _parse_reflection(
        self,
        reflection_text: str,
        period_start: float,
        period_end: float,
        sessions_analyzed: int,
        avg_score: float,
        error_analysis: ErrorAnalysis,
        waste_analysis: WasteAnalysis,
    ) -> ReflectionReport:
        """Parse model output into structured ReflectionReport.

        Tries JSON parse first, falls back to text extraction.
        """
        worst_patterns = []
        best_patterns = []
        recommendations = []
        tool_insights = {}

        # Try JSON parse
        try:
            data = json.loads(reflection_text)
            worst_patterns = data.get("worst_patterns", [])
            best_patterns = data.get("best_patterns", [])
            recommendations = data.get("recommendations", [])
            tool_insights = data.get("tool_insights", {})
        except json.JSONDecodeError:
            # Text-based extraction
            lines = reflection_text.split("\n")
            section = None
            for line in lines:
                stripped = line.strip()
                lower = stripped.lower()
                if ("worst" in lower and "pattern" in lower) or "最差模式" in stripped or "错误模式" in stripped:
                    section = "worst"
                elif ("best" in lower and "pattern" in lower) or "最佳模式" in stripped or "成功模式" in stripped:
                    section = "best"
                elif ("recommend" in lower) or "建议" in stripped:
                    section = "rec"
                elif stripped.startswith("- ") or stripped.startswith("* ") or stripped.startswith("• "):
                    item = stripped.lstrip("-*• ").strip()
                    if section == "worst":
                        worst_patterns.append(item)
                    elif section == "best":
                        best_patterns.append(item)
                    elif section == "rec":
                        recommendations.append(item)
                # Also handle numbered lists: "1. item" or "1) item"
                elif len(stripped) > 2 and stripped[0].isdigit() and stripped[1] in ".)" and stripped[2] == " ":
                    item = stripped[3:].strip()
                    if section == "worst":
                        worst_patterns.append(item)
                    elif section == "best":
                        best_patterns.append(item)
                    elif section == "rec":
                        recommendations.append(item)

        return ReflectionReport(
            period_start=period_start,
            period_end=period_end,
            sessions_analyzed=sessions_analyzed,
            avg_score=avg_score,
            error_summary=error_analysis.summary(),
            waste_summary=waste_analysis.summary(),
            worst_patterns=worst_patterns,
            best_patterns=best_patterns,
            tool_insights=tool_insights,
            recommendations=recommendations,
            model_used=self.config.get("primary", {}).get("model", "unknown"),
        )


# ── Default Prompt Template ──────────────────────────────────────────────

_DEFAULT_REFLECTION_PROMPT = """你是一个专业的AI agent性能分析专家。请分析以下 Hermes agent 的运行数据，识别问题模式和优化机会。

## 分析期间概况
- Session 数量: {sessions_count}
- 平均质量评分: {avg_score} (0-1 分)
- 工具调用总数: {total_invocations}
- 工具调用成功率: {success_rate}%

## 工具使用分布
{tool_usage}

## 结果信号分布
{signal_distribution}

## 错误分析
{error_summary}

## 时间浪费分析
{waste_summary}

---

请按以下 JSON 格式输出你的分析结果（不要输出其他内容）：

```json
{{
  "worst_patterns": [
    "描述1个最差模式",
    "描述第2个最差模式"
  ],
  "best_patterns": [
    "描述1个最佳模式"
  ],
  "tool_insights": {{
    "工具名": {{"success_rate": 0.95, "avg_duration_ms": 500, "recommendation": "建议"}}
  }},
  "recommendations": [
    "具体的可操作建议1",
    "具体的可操作建议2"
  ]
}}
```

重点关注：
1. 哪些错误是系统性的（重复出现）而非偶发的？
2. 哪些时间浪费可以通过策略调整避免？
3. 哪些成功模式值得固化为技能或策略？
4. 优先给出高影响、低风险的改进建议。
"""
