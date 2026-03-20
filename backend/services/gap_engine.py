"""
gap_engine.py – Pure-Python skill gap computation for PathForge.

No LLM calls. All logic is deterministic and unit-testable.

──────────────────────────────────────────────────────────────────────────────
Algorithm overview (for the README)
──────────────────────────────────────────────────────────────────────────────

Step 1 – Direct gap computation  (compute_gap)
    Compare the candidate's proficiency map against the role's required
    proficiency map on a skill-by-skill basis:

        For each skill s in required_skills:
          • candidate_level  = candidate_skills.get(s, 0)   # 0 = absent
          • required_level   = required_skills[s]
          • delta            = required_level - candidate_level

          delta ≤ 0  →  already_competent   (candidate meets or exceeds the bar)
          delta > 0  →  gap  (candidate needs to improve or start from scratch)
          candidate_level = 0 → also added to missing_entirely

        Gaps are sorted by delta descending so the highest-priority deficiencies
        appear first in every downstream list and UI rendering.

Step 2 – Prerequisite propagation  (propagate_prerequisites)
    The JD rarely lists foundational skills explicitly; an employer expects
    candidates to already know them.  This step walks the skills DAG upward
    (toward the roots) using BFS and inserts any prerequisite skill that the
    candidate does not yet fully possess.

    For each gap skill g:
      Walk the prerequisite chain via skills_graph[g]["prerequisites"].
      For each ancestor a:
        • If the candidate already meets the required level for a → skip.
        • Otherwise → add a to gaps with:
            current  = candidate_skills.get(a, 0)
            required = max(existing requirement, 1)   # minimum: awareness
            delta    = required - current
            origin   = "prerequisite_propagation"     # audit trail

    Propagated entries have lower implied priority than direct gaps because
    their delta is usually smaller (they are foundational, starter-level
    requirements).  The pathway builder respects the DAG order anyway via
    topological sort, so insertion order here doesn't matter.

Why pure Python?
    Gap computation is a deterministic business rule, not a fuzzy inference
    task.  Keeping it LLM-free means: fully reproducible results, zero
    latency from API round-trips, and straightforward unit testing.
──────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import logging
from collections import deque
from typing import Dict, List, Set

from models.schemas import GapResponse, SkillGapDetail

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────


def compute_gap(
    candidate_skills: Dict[str, int],
    required_skills: Dict[str, int],
) -> GapResponse:
    """
    Compute the skill gap between a candidate profile and a role's requirements.

    Parameters
    ----------
    candidate_skills:
        Map of skill_id → current proficiency (1–5) from the candidate's resume.
    required_skills:
        Map of skill_id → minimum required proficiency (1–5) from the JD.

    Returns
    -------
    GapResponse
        • gaps             – dict[skill_id, SkillGapDetail], sorted by delta ↓
        • already_competent – skill IDs where candidate meets or exceeds the bar
        • missing_entirely  – subset of gaps where candidate has zero proficiency
        • total_gap_score   – sum of all positive deltas (effort proxy)

    Algorithm
    ---------
    For every skill in required_skills:
        delta = required_level − candidate_level   (candidate_level=0 if absent)

        delta ≤ 0  → already_competent
        delta > 0  → gap entry  (+ missing_entirely when candidate_level == 0)

    Gaps are ordered by delta descending so the largest deficiencies are
    surfaced first; the pathway builder will later impose DAG ordering.
    """
    gaps_unsorted: Dict[str, SkillGapDetail] = {}
    already_competent: List[str] = []
    missing_entirely: List[str] = []

    for skill_id, required_level in required_skills.items():
        candidate_level = candidate_skills.get(skill_id, 0)
        delta = required_level - candidate_level

        if delta <= 0:
            # Candidate meets or exceeds the requirement
            already_competent.append(skill_id)
            logger.debug(
                "✓ %s: candidate=%d required=%d (surplus=%d)",
                skill_id, candidate_level, required_level, abs(delta),
            )
        else:
            # Genuine gap
            gaps_unsorted[skill_id] = SkillGapDetail(
                current=candidate_level,
                required=required_level,
                delta=delta,
            )
            if candidate_level == 0:
                missing_entirely.append(skill_id)
                logger.debug(
                    "✗✗ %s: MISSING ENTIRELY (required=%d)", skill_id, required_level
                )
            else:
                logger.debug(
                    "✗ %s: candidate=%d required=%d delta=%d",
                    skill_id, candidate_level, required_level, delta,
                )

    # Sort gaps by delta descending (highest-priority first)
    gaps_sorted: Dict[str, SkillGapDetail] = dict(
        sorted(gaps_unsorted.items(), key=lambda kv: kv[1].delta, reverse=True)
    )

    total_gap_score = sum(g.delta for g in gaps_sorted.values())

    logger.info(
        "Gap computation complete: %d gaps | %d already competent | "
        "%d missing entirely | total_gap_score=%d",
        len(gaps_sorted), len(already_competent),
        len(missing_entirely), total_gap_score,
    )

    return GapResponse(
        gaps=gaps_sorted,
        already_competent=already_competent,
        missing_entirely=missing_entirely,
        total_gap_score=total_gap_score,
    )


def propagate_prerequisites(
    gaps: Dict[str, SkillGapDetail],
    candidate_skills: Dict[str, int],
    skills_graph: Dict[str, dict],
) -> Dict[str, SkillGapDetail]:
    """
    Expand the gaps dict to include prerequisite skills from the DAG that the
    candidate does not yet possess, even if those skills were never mentioned
    in the job description.

    Parameters
    ----------
    gaps:
        The gaps dict produced by compute_gap (mutated copy is returned; the
        original is not modified).
    candidate_skills:
        Map of skill_id → current proficiency (1–5) for prerequisite checks.
    skills_graph:
        The full skills DAG loaded from skills_graph.json.  Each node must
        have at least a "prerequisites" key containing a list of skill IDs.

    Returns
    -------
    Dict[str, SkillGapDetail]
        Augmented gaps dict.  Propagated entries are added with:
            current  = candidate's actual level (or 0 if absent)
            required = max(1, existing requirement if already a gap)
            delta    = required - current
        Gaps originating from propagation are logged with origin="propagated".
        Sorting is preserved: direct gaps first (higher delta), then propagated
        entries appended in BFS discovery order.

    Algorithm – BFS from each gap skill toward the DAG roots
    ---------------------------------------------------------
    1.  Initialise the BFS frontier from all current gap skill IDs.
    2.  For each frontier node, look up its prerequisites in skills_graph.
    3.  For each prerequisite p:
          a. If p is already in gaps or already_competent → skip (already handled).
          b. Compute candidate_level = candidate_skills.get(p, 0).
          c. required_level = 1  (minimum: candidate must be at least at Awareness)
             (If p happens to already be a gap with a higher required level, keep that.)
          d. delta = required_level - candidate_level
          e. If delta > 0 → add to propagated (enqueue p for further BFS).
             If delta ≤ 0 → candidate already satisfies this prerequisite → skip.
    4.  Append all propagated entries to the original gaps dict (direct gaps
        retain their positions at the front, preserving delta-descending order).

    Example
    -------
    direct gap: "pandas"  (candidate has 0, requires 3, delta=3)
    pandas prerequisites in DAG: ["numpy"]
    numpy prerequisites in DAG:  ["python_basics"]
    candidate has no numpy, no python_basics
    → propagated gaps: {"numpy": {0,1,1}, "python_basics": {0,1,1}}
    Pathway builder will schedule: python_basics → numpy → pandas
    """
    # Work on a shallow copy so the caller's dict is unchanged
    augmented: Dict[str, SkillGapDetail] = dict(gaps)
    propagated_ids: Set[str] = set()  # track what we added in this call

    # BFS frontier initialised from existing gap skill IDs
    visited: Set[str] = set(augmented.keys())
    queue: deque[str] = deque(augmented.keys())

    while queue:
        skill_id = queue.popleft()

        node = skills_graph.get(skill_id)
        if node is None:
            logger.debug("Skill '%s' not found in skills_graph — skipping BFS.", skill_id)
            continue

        prerequisites: List[str] = node.get("prerequisites", [])

        for prereq_id in prerequisites:
            if prereq_id in visited:
                # Already processed (either a direct gap, already_competent,
                # or discovered earlier in this BFS traversal)
                continue

            visited.add(prereq_id)

            candidate_level = candidate_skills.get(prereq_id, 0)

            # Use required=1 as the baseline for propagated prerequisites.
            # If the prereq somehow already appears in the gaps dict with a
            # higher requirement (shouldn't happen here, but defensive), keep max.
            required_level = max(1, augmented.get(prereq_id, SkillGapDetail(
                current=0, required=1, delta=1
            )).required)

            delta = required_level - candidate_level

            if delta > 0:
                # Candidate doesn't meet even the minimum — insert as propagated gap
                augmented[prereq_id] = SkillGapDetail(
                    current=candidate_level,
                    required=required_level,
                    delta=delta,
                )
                propagated_ids.add(prereq_id)
                logger.debug(
                    "Propagated prerequisite gap: '%s' (origin: '%s') "
                    "current=%d required=%d delta=%d",
                    prereq_id, skill_id, candidate_level, required_level, delta,
                )
                # Continue BFS through this prerequisite's own prerequisites
                queue.append(prereq_id)
            else:
                logger.debug(
                    "Prerequisite '%s' already satisfied by candidate (level=%d) — skipping.",
                    prereq_id, candidate_level,
                )

    if propagated_ids:
        logger.info(
            "Prerequisite propagation added %d implicit gap(s): %s",
            len(propagated_ids),
            sorted(propagated_ids),
        )
    else:
        logger.info("Prerequisite propagation: no new gaps discovered.")

    return augmented


# ─────────────────────────────────────────────────────────────────────────────
# Convenience wrapper – used by the /gap router
# ─────────────────────────────────────────────────────────────────────────────

class GapEngine:
    """
    Stateless service class wrapping the two gap-computation functions.

    The skills_graph is injected at construction time so that the router can
    share a single loaded graph across requests without re-reading the file.
    """

    def __init__(self, skills_graph: Dict[str, dict]) -> None:
        """
        Parameters
        ----------
        skills_graph:
            Pre-loaded dict from skills_graph.json.
            Keys are skill IDs; values must contain at least {"prerequisites": [...]} .
        """
        self.skills_graph = skills_graph

    def compute(
        self,
        candidate_skills: Dict[str, int],
        required_skills: Dict[str, int],
        propagate: bool = True,
    ) -> GapResponse:
        """
        Full gap pipeline: direct gap computation + optional prerequisite propagation.

        Parameters
        ----------
        candidate_skills:
            Map of skill_id → proficiency (1–5).
        required_skills:
            Map of skill_id → required level (1–5).
        propagate:
            If True (default), run prerequisite propagation after the direct
            gap computation and merge results into the final GapResponse.

        Returns
        -------
        GapResponse
            Fully populated gap response, with propagated prerequisites merged
            into the gaps dict if propagate=True.
        """
        # 1. Direct gap
        result = compute_gap(candidate_skills, required_skills)

        if not propagate or not self.skills_graph:
            return result

        # 2. Propagate prerequisites into the gaps dict
        augmented_gaps = propagate_prerequisites(
            gaps=result.gaps,
            candidate_skills=candidate_skills,
            skills_graph=self.skills_graph,
        )

        # 3. Rebuild missing_entirely and total_gap_score to reflect propagated additions
        augmented_missing = [
            sid for sid, detail in augmented_gaps.items()
            if detail.current == 0
        ]
        augmented_total = sum(d.delta for d in augmented_gaps.values())

        return GapResponse(
            gaps=augmented_gaps,
            already_competent=result.already_competent,
            missing_entirely=augmented_missing,
            total_gap_score=augmented_total,
        )
