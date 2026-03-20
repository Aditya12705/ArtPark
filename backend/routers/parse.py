"""
routers/parse.py – POST /parse

Pipeline:
  1. Read valid skill_ids from app.state.skills_graph  (loaded at startup)
  2. Call GroqService.extract_skills(resume_text, jd_text, skill_ids)
  3. Return ParseResponse

Error surface:
  422  – Pydantic validation failure (FastAPI built-in)
  503  – Groq API unavailable or key missing
  500  – Unexpected server error
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import groq
from fastapi import APIRouter, Depends, HTTPException, Request

from models.schemas import ParseRequest, ParseResponse
from services.groq_service import GroqService

logger = logging.getLogger(__name__)
router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Dependency injection
# ─────────────────────────────────────────────────────────────────────────────

def get_groq_service() -> GroqService:
    """Return a fresh GroqService; the client is lazily created."""
    return GroqService()


def get_skills_graph(request: Request) -> Dict[str, Any]:
    """Pull the pre-loaded skills_graph from app.state."""
    return getattr(request.app.state, "skills_graph", {})


# ─────────────────────────────────────────────────────────────────────────────
# Route
# ─────────────────────────────────────────────────────────────────────────────

@router.post(
    "/",
    response_model=ParseResponse,
    summary="Extract structured skills from a resume and job description",
    responses={
        200: {"description": "Skills successfully extracted"},
        422: {"description": "Request body failed validation"},
        503: {"description": "Groq API unavailable"},
        500: {"description": "Unexpected server error"},
    },
)
async def parse_resume(
    payload: ParseRequest,
    groq_svc: GroqService      = Depends(get_groq_service),
    skills_graph: Dict[str, Any] = Depends(get_skills_graph),
) -> ParseResponse:
    """
    Extract candidate skills (from resume) and required skills (from JD)
    using Groq Llama-3.3-70B.  Only skill IDs present in `skills_graph.json`
    may appear in the response — all others are silently discarded
    (zero-hallucination enforcement via allowlist).

    **Proficiency scale:** 1 = Awareness → 5 = Expert
    """
    # Build the allowlist from the loaded graph
    skill_ids: List[str] = list(skills_graph.keys())
    if not skill_ids:
        logger.warning("/parse called but skills_graph is empty — proceeding with no allowlist.")

    logger.info(
        "/parse called: resume_len=%d jd_len=%d allowlist_size=%d",
        len(payload.resume_text), len(payload.jd_text), len(skill_ids),
    )

    try:
        result = await groq_svc.extract_skills(
            resume_text=payload.resume_text,
            jd_text=payload.jd_text,
            skill_ids=skill_ids,
        )
    except RuntimeError as exc:
        logger.error("Configuration error in /parse: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except groq.APIStatusError as exc:
        logger.error("Groq API error in /parse: status=%d msg=%s", exc.status_code, exc.message)
        raise HTTPException(
            status_code=503,
            detail=f"Groq API returned an error (HTTP {exc.status_code}). "
                   "Check your API key and quota.",
        ) from exc
    except groq.APIConnectionError as exc:
        logger.error("Groq connection error in /parse: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Could not reach the Groq API. Check your network connection.",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error in /parse")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}") from exc

    logger.info(
        "/parse success: %d candidate skills, %d required skills",
        len(result.candidate_skills), len(result.required_skills),
    )
    return result
