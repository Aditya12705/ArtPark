"""
routers/pathway.py – POST /pathway

Pipeline:
  1. Accept PathwayRequest (gaps dict + already_competent)
  2. Reconstruct a GapResponse from the raw gaps dict
  3. Inject PathwayBuilder with pre-loaded course_catalog + skills_graph
  4. Call PathwayBuilder.build()
     → build_pathway()           (topological sort, pure Python)
     → identify_skipped_courses() (pure Python)
     → generate_reasoning_traces() (single Claude call, with fallback)
  5. Assemble and return PathwayResponse

Error surface:
  422 – Pydantic validation failure (FastAPI built-in)
  503 – Anthropic API unavailable (reasoning traces fall back gracefully)
  500 – Unexpected server error
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from models.schemas import (
    CourseRecommendation,
    GapResponse,
    PathwayRequest,
    PathwayResponse,
    SkillGapDetail,
)
from services.pathway_builder import PathwayBuilder

logger = logging.getLogger(__name__)
router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Dependency injection
# ─────────────────────────────────────────────────────────────────────────────

def get_pathway_builder(request: Request) -> PathwayBuilder:
    """
    Construct a PathwayBuilder loaded with the pre-loaded course catalog and
    skills graph from app.state.  Stateless: cheap to instantiate per request.
    """
    course_catalog: List[Dict[str, Any]] = getattr(request.app.state, "course_catalog", [])
    skills_graph: Dict[str, Any]         = getattr(request.app.state, "skills_graph",   {})
    # Inject GroqService for reasoning traces
    from services.groq_service import GroqService
    return PathwayBuilder(course_catalog=course_catalog, skills_graph=skills_graph, groq_svc=GroqService())


# ─────────────────────────────────────────────────────────────────────────────
# Internal: reconstruct GapResponse from raw payload dicts
# ─────────────────────────────────────────────────────────────────────────────

def _reconstruct_gap_response(
    raw_gaps: Dict[str, Any],
    already_competent: List[str],
) -> GapResponse:
    """
    PathwayRequest carries gaps as a raw dict (so the client doesn't need to
    import SkillGapDetail).  This function re-hydrates it into a proper
    GapResponse that the PathwayBuilder expects.

    Acceptable incoming gap shapes:
        {"pandas": {"current": 1, "required": 3, "delta": 2}}   ← full dict
        {"pandas": 2}                                             ← delta-only int
    """
    gaps: Dict[str, SkillGapDetail] = {}
    missing_entirely: List[str]     = []

    for skill_id, value in raw_gaps.items():
        if isinstance(value, dict):
            current  = int(value.get("current",  0))
            required = int(value.get("required", current + 1))
            delta    = int(value.get("delta",    required - current))
        elif isinstance(value, (int, float)):
            # Treat a bare number as the delta; current unknown → assume 0
            delta    = int(value)
            current  = 0
            required = delta
        else:
            logger.warning("Unrecognised gap value for '%s': %r — skipping.", skill_id, value)
            continue

        # Clamp to valid ranges
        current  = max(0, min(5, current))
        required = max(1, min(5, required))
        delta    = max(0, delta)  # never negative in the gaps dict

        detail = SkillGapDetail(current=current, required=required, delta=delta)
        gaps[skill_id] = detail

        if current == 0:
            missing_entirely.append(skill_id)

    total_gap_score = sum(d.delta for d in gaps.values())

    return GapResponse(
        gaps=gaps,
        already_competent=already_competent,
        missing_entirely=missing_entirely,
        total_gap_score=total_gap_score,
    )


def _extract_candidate_skills(gaps: GapResponse) -> Dict[str, int]:
    """
    Derive a candidate_skills map from the gaps dict.
    Competent skills get their required level (they meet the bar by definition).
    """
    candidate: Dict[str, int] = {}
    for skill_id, detail in gaps.gaps.items():
        candidate[skill_id] = detail.current
    for skill_id in gaps.already_competent:
        # We don't have the exact level for competent skills; use 3 as a sane default
        candidate.setdefault(skill_id, 3)
    return candidate


# ─────────────────────────────────────────────────────────────────────────────
# Route
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/",
    response_model=PathwayResponse,
    summary="Generate an ordered, dependency-safe learning pathway",
    responses={
        200: {"description": "Pathway generated successfully"},
        422: {"description": "Request body failed validation"},
        503: {"description": "Anthropic API unavailable (reasoning traces will use fallback text)"},
        500: {"description": "Unexpected server error"},
    },
)
async def generate_pathway(
    payload: PathwayRequest,
    builder: PathwayBuilder = Depends(get_pathway_builder),
) -> PathwayResponse:
    """
    Build a personalised, prerequisite-ordered list of courses that close the
    candidate's skill gaps.

    **Inputs:** the `gaps` and `already_competent` fields from a `/gap` response
    (pass them through directly).

    **Output includes:**
    - `pathway` – ordered `CourseRecommendation` objects (complete before item N+1)
    - `skipped_courses` – courses the candidate already knows
    - `estimated_total_hours` – sum of all course durations
    - `reasoning_traces` – course_id → personalised one-sentence explanation

    > Reasoning traces are generated by a single Claude call.  If the Anthropic
    > API is unavailable, fallback template-based traces are returned automatically.
    """
    logger.info(
        "/pathway called: %d gap skills, %d already competent, max_courses=%s, level=%s",
        len(payload.gaps),
        len(payload.already_competent),
        payload.max_courses,
        payload.learner_level,
    )

    # Step 1: Re-hydrate raw dicts into typed models
    try:
        gap_response = _reconstruct_gap_response(
            raw_gaps=payload.gaps,
            already_competent=payload.already_competent,
        )
    except Exception as exc:
        logger.error("Failed to parse gaps in /pathway: %s", exc)
        raise HTTPException(
            status_code=422,
            detail=f"Could not interpret the 'gaps' field: {exc}",
        ) from exc

    if not gap_response.gaps:
        logger.info("/pathway: no gaps to address — returning empty pathway.")
        return PathwayResponse(
            pathway=[],
            skipped_courses=[],
            estimated_total_hours=0,
            reasoning_traces={},
            pathway_summary="No skill gaps detected. Your candidate is already qualified for this role!",
        )

    candidate_skills = _extract_candidate_skills(gap_response)

    # Step 2: Run the full pathway pipeline
    try:
        result: Dict[str, Any] = await builder.build(
            gaps=gap_response,
            candidate_skills=candidate_skills,
            already_competent=payload.already_competent,
            max_courses=payload.max_courses,
            max_hours=payload.max_hours if payload.max_hours is not None else None,
        )
    except Exception as exc:
        logger.exception("Unexpected error in /pathway")
        raise HTTPException(
            status_code=500,
            detail=f"Pathway generation failed: {exc}",
        ) from exc

    # Step 3: Assemble PathwayResponse
    pathway_steps: List[CourseRecommendation] = []
    traces = result.get("reasoning_traces", {})
    
    for course_dict in result.get("pathway", []):
        cid = course_dict["id"]
        # Map fields to match CourseRecommendation schema
        mapped_dict = {
            "course_id": cid,
            "title": course_dict.get("title", "Unknown Course"),
            "provider": course_dict.get("provider", "Internal"),
            "url": course_dict.get("url", "#"),
            "duration_hours": float(course_dict.get("duration_hours", 0)),
            "level": course_dict.get("level", "beginner"),
            "skills_addressed": course_dict.get("teaches", course_dict.get("covers_skills", [])),
            "reasoning": traces.get(cid, "Strategic choice to address your primary skill gaps."),
            "cognitive_load": course_dict.get("cognitive_load", "low")
        }
        pathway_steps.append(CourseRecommendation(**mapped_dict))

    total_hours: int = result.get("estimated_total_hours", 0)
    skipped: List[str] = result.get("skipped_courses", [])
    traces: Dict[str, str] = result.get("reasoning_traces", {}) # Keep for return if needed, though traces is merged above

    # Build a human-readable summary
    summary = _build_summary(
        n_courses=len(pathway_steps),
        n_gaps=len(gap_response.gaps),
        n_missing=len(gap_response.missing_entirely),
        total_hours=total_hours,
        skipped=skipped,
        max_hours=payload.max_hours,
    )

    logger.info(
        "/pathway success: %d courses | %d skipped | ~%d hours",
        len(pathway_steps), len(skipped), total_hours,
    )

    return PathwayResponse(
        pathway=pathway_steps,
        skipped_courses=skipped,
        estimated_total_hours=total_hours,
        reasoning_traces=traces,
        pathway_summary=summary,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_summary(
    n_courses: int,
    n_gaps: int,
    n_missing: int,
    total_hours: int,
    skipped: List[str],
    max_hours: Optional[int] = None,
) -> str:
    """Generate a 2–3 sentence narrative pathway summary."""
    missing_note = (
        f"{n_missing} of those skill(s) are entirely absent from your profile. "
        if n_missing
        else ""
    )
    skip_note = (
        f"{len(skipped)} course(s) were skipped because you are already competent in their content. "
        if skipped
        else ""
    )
    budget_note = (
        f"Pathway trimmed to your {max_hours}-hour budget — additional gaps may need separate sprints. "
        if max_hours is not None and total_hours >= max_hours - 5
        else ""
    )
    return (
        f"Your personalised pathway addresses {n_gaps} skill gap(s) across {n_courses} course(s) "
        f"(approximately {total_hours} hours of learning). "
        f"{missing_note}"
        f"{budget_note}"
        f"{skip_note}"
        "Courses are ordered so each one's prerequisites are always covered before it."
    ).strip()
