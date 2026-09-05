"""
Self Evolution Plugin — Cron Job Registration
==============================================

Registers two cron jobs:
  1. dream_time (1:00):  Run dream consolidation
  2. propose_time (19:00): Push proposals via Feishu

Uses Hermes' existing cron system (cron/jobs.json).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

from self_evolution.paths import CRON_DIR

CRON_FILE = CRON_DIR / "jobs.json"

DREAM_JOB_ID = "self_evolution_dream"
PROPOSE_JOB_ID = "self_evolution_propose"


def register_cron_jobs():
    """Register the two self_evolution cron jobs if not already present."""
    CRON_DIR.mkdir(parents=True, exist_ok=True)

    jobs = _load_jobs()

    # Resolve model config from hermes unified config
    from self_evolution.reflection_engine import _resolve_runtime_config
    runtime = _resolve_runtime_config()
    model = runtime.get("model", "")
    provider = runtime.get("provider", "")

    # Dream consolidation at 1:00
    if not any(j.get("id") == DREAM_JOB_ID for j in jobs):
        jobs.append({
            "id": DREAM_JOB_ID,
            "name": "Self Evolution - Dream Consolidation",
            "prompt": "运行自我进化的梦境整理：分析前日session的错误和浪费时间问题，生成进化提案。",
            "schedule": "0 1 * * *",
            "model": model,
            "provider": provider,
            "deliver": "[SILENT]",
            "skill": "self_evolution:dream",
        })

    # Proposal push at 19:00
    if not any(j.get("id") == PROPOSE_JOB_ID for j in jobs):
        jobs.append({
            "id": PROPOSE_JOB_ID,
            "name": "Self Evolution - Proposal Push",
            "prompt": "推送今日自我进化提案到飞书。",
            "schedule": "0 19 * * *",
            "model": model,
            "provider": provider,
            "deliver": "[SILENT]",
            "skill": "self_evolution:propose",
        })

    _save_jobs(jobs)
    logger.info("Registered self_evolution cron jobs: dream=1:00, propose=19:00")


def run_dream_job():
    """Execute the dream consolidation job.

    Called by the cron system at 1:00.
    Uses hermes unified runtime provider for model config.
    """
    from self_evolution.reflection_engine import DreamEngine

    # DreamEngine() with no args auto-resolves via resolve_runtime_provider()
    engine = DreamEngine()
    report = engine.run(hours=24, max_runtime_seconds=6 * 3600)

    if report:
        logger.info("Dream consolidation complete: score=%.3f, proposals generated", report.avg_score)
    else:
        logger.info("Dream consolidation: no data to analyze")


def run_propose_job():
    """Execute the proposal push job.

    Called by the cron system at 19:00.

    Includes auto-compensation: if recent reflection reports have no
    corresponding proposals, generates them before pushing to Feishu.
    """
    _compensate_proposals()

    from self_evolution.feishu_notifier import FeishuNotifier

    notifier = FeishuNotifier()
    notifier.send_daily_report()


def _compensate_proposals():
    """Generate proposals for recent reports that have none.

    Handles the case where DreamEngine ran but generate_proposals was
    skipped (e.g. hermes agent cron executed report creation without
    calling the proposal step).
    """
    from self_evolution import db
    import json
    import time

    # Find reports from the last 3 days that have no proposals
    cutoff = time.time() - (3 * 86400)
    recent_reports = db.fetch_all(
        "reflection_reports",
        where="created_at >= ?",
        params=(cutoff,),
        order_by="created_at DESC",
    )

    if not recent_reports:
        return

    # Get report IDs that already have proposals
    existing = db.fetch_all("evolution_proposals", where="1=1")
    covered_ids = {row.get("report_id") for row in existing if row.get("report_id")}

    generated = 0
    for report_row in recent_reports:
        rid = report_row.get("id")
        if rid is None or rid in covered_ids:
            continue

        # Reconstruct a minimal ReflectionReport for proposal generation
        from self_evolution.models import ReflectionReport
        report = ReflectionReport(
            period_start=report_row.get("period_start", 0),
            period_end=report_row.get("period_end", 0),
            sessions_analyzed=report_row.get("sessions_analyzed", 0),
            avg_score=report_row.get("avg_score", 0),
            error_summary=report_row.get("error_summary", ""),
            waste_summary=report_row.get("waste_summary", ""),
            worst_patterns=json.loads(report_row.get("worst_patterns", "[]") or "[]"),
            best_patterns=json.loads(report_row.get("best_patterns", "[]") or "[]"),
            recommendations=json.loads(report_row.get("recommendations", "[]") or "[]"),
        )

        from self_evolution.evolution_proposer import generate_proposals
        proposals = generate_proposals(report, report_id=rid)
        for p in proposals:
            try:
                db.insert("evolution_proposals", p.to_db_row())
                generated += 1
            except Exception:
                pass

    if generated:
        logger.info("Compensated %d proposals from orphaned reports", generated)


def _load_jobs() -> list:
    """Load existing cron jobs."""
    if not CRON_FILE.exists():
        return []
    try:
        return json.loads(CRON_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save_jobs(jobs: list):
    """Save cron jobs."""
    CRON_FILE.write_text(
        json.dumps(jobs, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
