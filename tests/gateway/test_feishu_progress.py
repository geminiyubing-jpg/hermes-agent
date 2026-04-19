"""Tests for ProgressCard — card structure, quality step detection, and constants.

Tests the dataclass in isolation without requiring a real Feishu adapter or lark_oapi SDK.
"""

import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from gateway.feishu_progress import ProgressCard, StepInfo, _STATUS_ICONS, _QUALITY_STEP_KEYWORDS


class TestConstants(unittest.TestCase):
    """Verify module-level constants exist and have expected values."""

    def test_status_icons_has_required_keys(self):
        for key in ("pending", "running", "done", "failed"):
            self.assertIn(key, _STATUS_ICONS)
            self.assertIsInstance(_STATUS_ICONS[key], str)
            self.assertTrue(len(_STATUS_ICONS[key]) > 0)

    def test_quality_step_keywords_includes_chinese_and_english(self):
        self.assertIn("质量", _QUALITY_STEP_KEYWORDS)
        self.assertIn("验收", _QUALITY_STEP_KEYWORDS)
        self.assertIn("quality", _QUALITY_STEP_KEYWORDS)
        self.assertIn("check", _QUALITY_STEP_KEYWORDS)

    def test_quality_step_keywords_is_frozenset(self):
        self.assertIsInstance(_QUALITY_STEP_KEYWORDS, frozenset)


class TestBuildCard(unittest.TestCase):
    """Tests for _build_card card structure."""

    def _make_card(self, **overrides):
        adapter = Mock()
        defaults = dict(
            adapter=adapter,
            chat_id="oc_test",
            metadata=None,
        )
        defaults.update(overrides)
        card = ProgressCard(**defaults)
        return card

    def test_empty_card_has_config_and_header(self):
        card = self._make_card()
        result = card._build_card()
        self.assertIn("config", result)
        self.assertIn("header", result)
        self.assertIn("elements", result)
        self.assertTrue(result["config"]["wide_screen_mode"])
        self.assertIn("title", result["header"])

    def test_task_summary_appears_in_elements(self):
        card = self._make_card()
        card._task_summary = "Test task description"
        result = card._build_card()
        md_elements = [e for e in result["elements"] if e.get("tag") == "markdown"]
        self.assertTrue(any("Test task description" in e.get("content", "") for e in md_elements))

    def test_steps_appear_with_status_icons(self):
        card = self._make_card()
        card._steps = [
            StepInfo(name="Step A", status="done"),
            StepInfo(name="Step B", status="running"),
            StepInfo(name="Step C", status="failed"),
        ]
        result = card._build_card()
        md_contents = [e.get("content", "") for e in result["elements"] if e.get("tag") == "markdown"]
        joined = " ".join(md_contents)
        self.assertIn("Step A", joined)
        self.assertIn("Step B", joined)
        self.assertIn("Step C", joined)
        # Check icons appear
        self.assertIn(_STATUS_ICONS["done"], joined)
        self.assertIn(_STATUS_ICONS["running"], joined)
        self.assertIn(_STATUS_ICONS["failed"], joined)

    def test_non_final_card_has_blue_template(self):
        card = self._make_card()
        card._finalized = False
        result = card._build_card()
        self.assertEqual(result["header"]["template"], "blue")

    def test_finalized_success_card_has_green_template(self):
        card = self._make_card()
        card._finalized = True
        card._title = "任务完成 (耗时 10秒)"
        result = card._build_card()
        self.assertEqual(result["header"]["template"], "green")

    def test_finalized_failure_card_has_red_template(self):
        card = self._make_card()
        card._finalized = True
        card._title = "任务失败 (耗时 10秒)"
        result = card._build_card()
        self.assertEqual(result["header"]["template"], "red")


class TestFinalizeQualityStep(unittest.TestCase):
    """Tests for finalize() quality step dedup logic."""

    def _make_card(self):
        adapter = Mock()
        card = ProgressCard(adapter=adapter, chat_id="oc_test", metadata=None)
        card._card_msg_id = "om_card"
        card._start_ts = time.time()
        return card

    def test_quality_step_added_when_not_present(self):
        card = self._make_card()
        card._steps = [StepInfo(name="Analyze code"), StepInfo(name="Generate fix")]
        card._finalized = False

        with patch.object(card, "_do_edit", new_callable=AsyncMock) as mock_edit:
            import asyncio
            asyncio.run(card.finalize("Done", success=True))

        step_names = [s.name for s in card._steps]
        self.assertIn("质量验收", step_names)

    def test_quality_step_not_duplicated_when_keyword_present(self):
        card = self._make_card()
        card._steps = [StepInfo(name="质量验收"), StepInfo(name="Generate fix")]
        card._finalized = False

        with patch.object(card, "_do_edit", new_callable=AsyncMock):
            import asyncio
            asyncio.run(card.finalize("Done", success=True))

        quality_count = sum(1 for s in card._steps if "质量" in s.name)
        self.assertEqual(quality_count, 1)

    def test_english_quality_keyword_also_prevents_duplicate(self):
        card = self._make_card()
        card._steps = [StepInfo(name="Quality check"), StepInfo(name="Deploy")]
        card._finalized = False

        with patch.object(card, "_do_edit", new_callable=AsyncMock):
            import asyncio
            asyncio.run(card.finalize("Done", success=True))

        # "Quality check" contains "quality" keyword, so no extra step
        quality_count = sum(1 for s in card._steps if any(kw in s.name.lower() for kw in _QUALITY_STEP_KEYWORDS))
        self.assertEqual(quality_count, 1)

    def test_no_quality_step_when_no_steps(self):
        card = self._make_card()
        card._steps = []
        card._finalized = False

        with patch.object(card, "_do_edit", new_callable=AsyncMock):
            import asyncio
            asyncio.run(card.finalize("Done", success=True))

        # No steps at all, so no quality step added
        self.assertEqual(len(card._steps), 0)


class TestProgressCardIsActive(unittest.TestCase):
    """Tests for is_active property."""

    def test_active_when_has_msg_id_and_not_finalized(self):
        card = ProgressCard(adapter=Mock(), chat_id="oc_test")
        card._card_msg_id = "om_123"
        card._finalized = False
        self.assertTrue(card.is_active)

    def test_not_active_when_no_msg_id(self):
        card = ProgressCard(adapter=Mock(), chat_id="oc_test")
        card._card_msg_id = None
        self.assertFalse(card.is_active)

    def test_not_active_when_finalized(self):
        card = ProgressCard(adapter=Mock(), chat_id="oc_test")
        card._card_msg_id = "om_123"
        card._finalized = True
        self.assertFalse(card.is_active)
