"""
routers/gap.py – POST /gap

Pipeline:
  1. Accept GapRequest (candidate_skills + required_skills)
  2. Build GapEngine with the pre-loaded skills_graph
  3. Call GapEngine.compute(propagate=True)
     → internally runs compute_gap() + propagate_prerequisites()
  4. Return GapResponse

Error surface:
  422 – Pydantic validation failure (FastAPI built-in)
  500 – Unexpected server error
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request

from models.schemas import GapRequest, GapResponse
from services.gap_engine import GapEngine

logger = logging.getLogger(__name__)
router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Dependency injection
# ─────────────────────────────────────────────────────────────────────────────

def get_gap_engine(request: Request) -> GapEngine:
    """
    Build a GapEngine seeded with the pre-loaded skills_graph from app.state.
    The engine is stateless so a new instance per request is cheap.
    """
    skills_graph: Dict[str, Any] = getattr(request.app.state, "skills_graph", {})
    return GapEngine(skills_graph=skills_graph)


# ─────────────────────────────────────────────────────────────────────────────
# Route
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/",
    response_model=GapResponse,
    summary="Compute skill gaps and propagate implicit prerequisites",
    responses={
        200: {"description": "Gap analysis complete"},
        422: {"description": "Request body failed validation"},
        500: {"description": "Unexpected server error"},
    },
)
async def compute_gap(
    payload: GapRequest,
    engine: GapEngine = Depends(get_gap_engine),
) -> GapResponse:
    """
    Compare the candidate's current proficiency map against the role's required
    proficiency map and return:

    - **gaps** – skill_id → {current, required, delta}, sorted by delta ↓
    - **already_competent** – skills where candidate meets or exceeds the bar
    - **missing_entirely** – skills the candidate has zero proficiency in
    - **total_gap_score** – Σ deltas (effort proxy)

    Prerequisite propagation is **on by default**: if `pandas` is a gap and
    the candidate lacks `numpy`, `numpy` is automatically added to the gaps dict.
    """
    logger.info(
        "/gap called: %d candidate skills, %d required skills",
        len(payload.candidate_skills), len(payload.required_skills),
    )

    try:
        result = engine.compute(
            candidate_skills=payload.candidate_skills,
            required_skills=payload.required_skills,
            propagate=True,
        )
    except Exception as exc:
        logger.exception("Unexpected error in /gap")
        raise HTTPException(
            status_code=500,
            detail=f"Gap computation failed: {exc}",
        ) from exc

    logger.info(
        "/gap success: %d gaps | %d already competent | %d missing entirely | score=%d",
        len(result.gaps),
        len(result.already_competent),
        len(result.missing_entirely),
        result.total_gap_score or 0,
    )
    return result
