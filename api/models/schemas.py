"""
schemas.py – Pydantic v2 models for all PathForge request / response types.

Proficiency scale (1–5):
  1 = Awareness     – knows the concept exists
  2 = Beginner      – can work with guidance
  3 = Intermediate  – works independently on most tasks
  4 = Advanced      – deep expertise, can mentor others
  5 = Expert        – industry-leading, can define standards
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# Shared / primitive types
# ─────────────────────────────────────────────────────────────────────────────

# Proficiency level constraint reused across models
_PROF_FIELD_KWARGS = dict(ge=1, le=5)


class SkillGapDetail(BaseModel):
    """Per-skill breakdown produced by the gap engine."""

    current: int = Field(
        ...,
        ge=0,
        le=5,
        description=(
            "Candidate's current proficiency level (0 = not present, 1–5 scale). "
            "0 means the skill is completely absent from the candidate's profile."
        ),
    )
    required: int = Field(
        ...,
        **_PROF_FIELD_KWARGS,
        description="Minimum proficiency level required by the job description (1–5 scale).",
    )
    delta: int = Field(
        ...,
        description=(
            "Gap = required − current. "
            "Positive → candidate needs to improve; "
            "0 → already meets the bar; "
            "negative → over-qualified."
        ),
    )


class CourseRecommendation(BaseModel):
    """A single course recommended inside a learning pathway."""

    course_id: str = Field(
        ...,
        description="Stable unique identifier matching a course in course_catalog.yaml.",
    )
    title: str = Field(
        ...,
        description="Human-readable course title as it appears in the catalog.",
    )
    provider: Optional[str] = Field(
        None,
        description="Logo or name of the platform hosting the course (e.g. 'Coursera').",
    )
    url: Optional[str] = Field(
        None,
        description="Direct link to the course platform.",
    )
    duration_hours: float = Field(
        ...,
        gt=0,
        description="Estimated completion time in hours.",
    )
    level: str = Field(
        ...,
        description="Difficulty level: 'beginner', 'intermediate', or 'advanced'.",
        pattern=r"^(beginner|intermediate|advanced)$",
    )
    skills_addressed: List[str] = Field(
        ...,
        description="List of skill IDs from skills_graph.json that this course teaches.",
    )
    reasoning: str = Field(
        ...,
        description=(
            "One- or two-sentence explanation of why this specific course was chosen "
            "for this candidate at this point in the pathway."
        ),
    )
    cognitive_load: Optional[str] = Field(
        "low",
        description="Difficulty level for load balancing: 'low', 'medium', or 'high'.",
    )


# ─────────────────────────────────────────────────────────────────────────────
# POST /parse
# ─────────────────────────────────────────────────────────────────────────────

class ParseRequest(BaseModel):
    """Input for the /parse endpoint: raw resume text + job description text."""

    resume_text: str = Field(
        ...,
        min_length=50,
        description=(
            "Full text of the candidate's resume or LinkedIn profile. "
            "Minimum 50 characters. Plain text preferred; HTML/PDF extracted text accepted."
        ),
    )
    jd_text: str = Field(
        ...,
        min_length=50,
        description=(
            "Full text of the target job description. "
            "Used to extract the required skill set and proficiency expectations."
        ),
    )


class ParseResponse(BaseModel):
    """Structured skills extracted from both the resume and the job description."""

    candidate_skills: Dict[str, Dict[str, int]] = Field(
        ...,
        description=(
            "Map of skill_id → {level: 1–5, last_used_year: int} inferred from the resume. "
            "Only skills that Claude is confident about are included."
        ),
    )
    required_skills: Dict[str, int] = Field(
        ...,
        description=(
            "Map of skill_id → minimum required proficiency level (1–5) extracted "
            "from the job description. Reflects what the role demands."
        ),
    )
    raw_resume_skills: List[str] = Field(
        ...,
        description=(
            "Human-readable skill labels as literally extracted from the resume "
            "(before mapping to canonical skill IDs). Useful for debugging and transparency."
        ),
    )
    raw_jd_skills: List[str] = Field(
        ...,
        description=(
            "Human-readable skill labels as literally extracted from the job description "
            "(before mapping to canonical skill IDs)."
        ),
    )
    model_used: Optional[str] = Field(
        None,
        description="Identifier of the LLM model that performed the extraction, e.g. 'claude-opus-4-5'.",
    )
    extraction_confidence: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description=(
            "Overall confidence score for the extraction (0.0–1.0). "
            "Low scores suggest the input text was ambiguous or too short."
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# POST /gap
# ─────────────────────────────────────────────────────────────────────────────

class GapRequest(BaseModel):
    """Input for the /gap endpoint: candidate's current skills vs. required skills."""

    candidate_skills: Dict[str, Dict[str, int]] = Field(
        ...,
        description=(
            "Map of skill_id → {level: 1–5, last_used_year: int}. "
            "Used to compute temporal skill decay before gap analysis."
        ),
    )
    required_skills: Dict[str, int] = Field(
        ...,
        description=(
            "Map of skill_id → required proficiency (1–5). "
            "Typically taken directly from ParseResponse.required_skills."
        ),
    )


class GapResponse(BaseModel):
    """Result of comparing candidate skills to job requirements."""

    gaps: Dict[str, SkillGapDetail] = Field(
        ...,
        description=(
            "Map of skill_id → SkillGapDetail for every skill where the candidate "
            "does not fully meet the requirement (delta > 0) or is missing entirely (current=0)."
        ),
    )
    already_competent: List[str] = Field(
        ...,
        description=(
            "Skill IDs where the candidate meets or exceeds the required proficiency "
            "(delta ≤ 0). No learning action needed for these."
        ),
    )
    missing_entirely: List[str] = Field(
        ...,
        description=(
            "Subset of gap skill IDs where the candidate has zero proficiency (current=0). "
            "These are the highest-priority items to address."
        ),
    )
    total_gap_score: Optional[int] = Field(
        None,
        ge=0,
        description=(
            "Sum of all positive deltas across gap skills. "
            "Higher = larger overall gap. Useful for ranking candidates or estimating effort."
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# POST /pathway
# ─────────────────────────────────────────────────────────────────────────────

class PathwayRequest(BaseModel):
    """Input for the /pathway endpoint: gap analysis output used to build the plan."""

    gaps: Dict[str, Any] = Field(
        ...,
        description=(
            "The gaps dict from GapResponse — map of skill_id → {current, required, delta}. "
            "Used to decide which courses to include and in what order."
        ),
    )
    already_competent: List[str] = Field(
        default_factory=list,
        description=(
            "Skill IDs the candidate already meets. Courses that exclusively teach "
            "these skills are skipped to avoid redundant learning."
        ),
    )
    max_courses: Optional[int] = Field(
        10,
        ge=1,
        le=50,
        description="Maximum number of courses to include in the pathway. Defaults to 10.",
    )
    max_hours: Optional[int] = Field(
        None,
        ge=1,
        description="Optional HR time budget constraint in hours. Pathway will be truncated to fit this budget.",
    )
    learner_level: Optional[str] = Field(
        "beginner",
        description=(
            "Overall self-reported learner level used as a tiebreaker when multiple "
            "courses cover the same skill. Options: 'beginner', 'intermediate', 'advanced'."
        ),
        pattern=r"^(beginner|intermediate|advanced)$",
    )
    preferred_providers: Optional[List[str]] = Field(
        None,
        description=(
            "Optional list of preferred course providers (e.g. ['Coursera', 'Udemy']). "
            "Matching providers are ranked higher when skills coverage is equal."
        ),
    )


class PathwayResponse(BaseModel):
    """An ordered, dependency-respecting learning pathway for the candidate."""

    pathway: List[CourseRecommendation] = Field(
        ...,
        description=(
            "Ordered list of recommended courses in the sequence the candidate should "
            "complete them (earlier items satisfy prerequisites for later ones)."
        ),
    )
    skipped_courses: List[str] = Field(
        ...,
        description=(
            "Course IDs that were considered but skipped because the candidate is already "
            "competent in all skills the course teaches."
        ),
    )
    estimated_total_hours: int = Field(
        ...,
        ge=0,
        description="Sum of duration_hours across all recommended courses, rounded to the nearest hour.",
    )
    reasoning_traces: Dict[str, str] = Field(
        ...,
        description=(
            "Map of course_id → one-sentence explanation of why this course was chosen "
            "for this specific candidate. Surfaced in the UI for transparency."
        ),
    )
    pathway_summary: Optional[str] = Field(
        None,
        description=(
            "A 2–3 sentence narrative summarising the overall learning plan, "
            "estimated duration, and key milestones."
        ),
    )
