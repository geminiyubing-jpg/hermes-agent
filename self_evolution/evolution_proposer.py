"""
Self Evolution Plugin — Evolution Proposer
===========================================

Converts reflection insights into concrete, actionable evolution proposals.

Each proposal includes:
  - type: skill | strategy | memory | tool_preference
  - title: short description
  - description: detailed change
  - expected_impact: what improvement to expect
  - risk_assessment: low | medium | high
  - rollback_plan: how to revert
"""

from __future__ import annotations

import logging
import uuid
from typing import List

from self_evolution.models import Proposal, ReflectionReport

logger = logging.getLogger(__name__)


def generate_proposals(report: ReflectionReport, report_id: int) -> List[Proposal]:
    """Generate evolution proposals from a reflection report.

    Prioritizes proposals by:
    1. Impact (fixes for systemic errors > optimizations > enhancements)
    2. Risk (low risk first)
    3. Feasibility (clear rollback plan)
    """
    proposals = []

    # 1. Proposals from worst patterns (error-driven)
    for i, pattern in enumerate(report.worst_patterns):
        proposal = _error_to_proposal(pattern, report, report_id, i)
        if proposal:
            proposals.append(proposal)

    # 2. Proposals from best patterns (success-driven)
    for i, pattern in enumerate(report.best_patterns):
        proposal = _success_to_proposal(pattern, report, report_id, i)
        if proposal:
            proposals.append(proposal)

    # 3. Proposals from recommendations
    for i, rec in enumerate(report.recommendations):
        proposal = _recommendation_to_proposal(rec, report, report_id, i)
        if proposal:
            proposals.append(proposal)

    # Deduplicate by title similarity
    proposals = _deduplicate(proposals)

    # Cap at 5 proposals per day
    return proposals[:5]


def _error_to_proposal(
    pattern: str, report: ReflectionReport, report_id: int, index: int
) -> Proposal:
    """Convert an error pattern into a proposal."""
    return Proposal(
        id=f"prop-error-{uuid.uuid4().hex[:8]}",
        report_id=report_id,
        proposal_type="strategy",
        title=f"规避模式: {pattern[:50]}",
        description=f"基于错误分析发现的问题模式: {pattern}\n\n"
                    f"建议创建策略规则来规避此类问题。",
        expected_impact="减少同类错误发生率",
        risk_assessment="low",
        rollback_plan="删除策略规则即可恢复",
        status="pending_approval",
    )


def _success_to_proposal(
    pattern: str, report: ReflectionReport, report_id: int, index: int
) -> Proposal:
    """Convert a success pattern into a proposal (skill creation)."""
    return Proposal(
        id=f"prop-success-{uuid.uuid4().hex[:8]}",
        report_id=report_id,
        proposal_type="skill",
        title=f"固化成功模式: {pattern[:50]}",
        description=f"基于成功分析发现的高效模式: {pattern}\n\n"
                    f"建议创建可复用的技能来固化此模式。",
        expected_impact="提高同类任务效率",
        risk_assessment="low",
        rollback_plan="删除创建的技能即可恢复",
        status="pending_approval",
    )


def _recommendation_to_proposal(
    rec: str, report: ReflectionReport, report_id: int, index: int
) -> Proposal:
    """Convert a recommendation into a proposal."""
    # Detect type from content
    proposal_type = "strategy"
    if any(kw in rec for kw in ["记忆", "记忆更新", "memory", "记住"]):
        proposal_type = "memory"
    elif any(kw in rec for kw in ["技能", "skill", "创建"]):
        proposal_type = "skill"
    elif any(kw in rec for kw in ["工具", "tool", "偏好"]):
        proposal_type = "tool_preference"

    return Proposal(
        id=f"prop-rec-{uuid.uuid4().hex[:8]}",
        report_id=report_id,
        proposal_type=proposal_type,
        title=f"优化建议: {rec[:50]}",
        description=rec,
        expected_impact="提升整体agent性能",
        risk_assessment="low",
        rollback_plan="移除变更即可恢复",
        status="pending_approval",
    )


def _deduplicate(proposals: List[Proposal]) -> List[Proposal]:
    """Remove proposals with very similar titles."""
    seen_titles = set()
    unique = []
    for p in proposals:
        # Normalize title for comparison
        normalized = p.title.lower().strip()[:30]
        if normalized not in seen_titles:
            seen_titles.add(normalized)
            unique.append(p)
    return unique
