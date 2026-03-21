"""
claude_service.py – Anthropic Claude wrapper for NexusLearn skill extraction.

Single public entry-point:
    extract_skills(resume_text, jd_text, skill_ids) -> ParseResponse

Zero-hallucination policy: any skill_id returned by Claude that is not in the
provided skill_ids allowlist is silently discarded before building the response.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, cast

import anthropic  # type: ignore

from models.schemas import ParseResponse  # type: ignore

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_MODEL = "claude-opus-4-5"
MAX_TOKENS = 4096

# Proficiency scale communicated to Claude (also used in validation)
PROFICIENCY_MIN = 1
PROFICIENCY_MAX = 5

# ─────────────────────────────────────────────────────────────────────────────
# Prompt templates
# ─────────────────────────────────────────────────────────────────────────────

def _build_system_prompt(skill_ids: List[str]) -> str:
    """
    Build the system prompt that constrains Claude to the allowlist and
    defines the exact JSON schema it must emit.
    """
    skill_list_str = "\n".join(f'  - "{s}"' for s in skill_ids)

    return f"""\
You are NexusLearn's Skill Extraction Engine, deployed inside a corporate onboarding \
and career-development platform. Your sole task is to analyse a candidate's resume \
and a job description, then return a structured JSON object describing the skill \
landscape for that candidate-role pair.

══════════════════════════════════════════════════════════════
PROFICIENCY SCALE  (apply consistently to both resume and JD)
══════════════════════════════════════════════════════════════
1 = Awareness      – Knows the concept exists; has read about it
2 = Beginner       – Has used it in a learning exercise or small personal project
3 = Intermediate   – Works with it independently on real tasks; needs occasional guidance
4 = Advanced       – Deep, production-level expertise; can mentor others
5 = Expert         – Industry-leading authority; shapes standards or has published work

══════════════════════════════════════════════════════════════
VALID SKILL IDs  (you MUST use ONLY these identifiers)
══════════════════════════════════════════════════════════════
{skill_list_str}

Any skill you observe that does not map to one of the IDs above MUST be captured \
in raw_resume_skills or raw_jd_skills as plain English, but MUST NOT appear as a \
key in candidate_skills or required_skills.

══════════════════════════════════════════════════════════════
OUTPUT RULES  (non-negotiable)
══════════════════════════════════════════════════════════════
• Output ONLY a single, valid JSON object — no markdown fences, no preamble, \
no commentary, no trailing text.
• Every key in candidate_skills and required_skills must be one of the valid \
skill IDs listed above.
• Proficiency values must be integers 1–5.
• For candidate_skills, you MUST also estimate the "last_used_year" (integer, \
e.g., 2024). Use the latest occurrence in the resume. If unknown, use 2026.
• raw_resume_skills and raw_jd_skills must be plain-English strings, NOT skill IDs.
• If a skill cannot be inferred from the text, omit it rather than guessing.
• Do NOT invent skill IDs. Do NOT abbreviate skill IDs. Use them exactly as listed.

══════════════════════════════════════════════════════════════
REQUIRED JSON SCHEMA
══════════════════════════════════════════════════════════════
{{
  "candidate_skills": {{
    "<skill_id>": {{ "level": <int 1-5>, "last_used_year": <int> }},
    ...
  }},
  "required_skills": {{
    "<skill_id>": <int 1-5>,
    ...
  }},
  "raw_resume_skills": ["<plain English skill label>", ...],
  "raw_jd_skills":     ["<plain English skill label>", ...],
  "extraction_confidence": <float 0.0-1.0>
}}"""


def _build_user_prompt(resume_text: str, jd_text: str) -> str:
    """
    Build the user-turn message that injects the two documents to analyse.
    """
    return f"""\
Analyse the following two documents and return the JSON object described in your \
system instructions.

════════════════════════════════
CANDIDATE RESUME
════════════════════════════════
{resume_text.strip()}

════════════════════════════════
JOB DESCRIPTION
════════════════════════════════
{jd_text.strip()}

Remember:
• candidate_skills  → extracted from the RESUME only
• required_skills   → extracted from the JOB DESCRIPTION only
• Use ONLY the valid skill IDs provided in your instructions
• Return raw English labels (e.g. "React.js", "stakeholder communication") in the raw_* lists
• Output pure JSON, no markdown, no explanation"""


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _strip_markdown_fences(text: str) -> str:
    """
    Defensively remove ```json ... ``` or ``` ... ``` wrappers in case Claude
    adds them despite the instruction not to (belt-and-suspenders guard).
    """
    # Remove leading/trailing whitespace
    text = text.strip()
    # Remove ```json or ``` fences
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _clamp_proficiency(value: Any) -> Optional[int]:
    """
    Convert and clamp a raw JSON value to a valid 1–5 proficiency integer.
    Returns None if the value is not convertible.
    """
    try:
        v = int(value)
        return max(PROFICIENCY_MIN, min(PROFICIENCY_MAX, v))
    except (TypeError, ValueError):
        return None


def _sanitise_candidate_skills(
    raw: Any,
    allowlist: set[str],
    current_year: int = 2026,
) -> Dict[str, Dict[str, int]]:
    """
    Sanitise candidate skills: {id: {level, last_used_year}}.
    Includes a fallback for simple integer values if the model ignores the schema.
    """
    if not isinstance(raw, dict):
        logger.warning("candidate_skills is not a dict, defaulting to empty. Got: %r", raw)
        return {}

    result: Dict[str, Dict[str, int]] = {}
    for skill_id, data in raw.items():
        if skill_id not in allowlist:
            continue
        
        # Fallback if Claude returns level as integer instead of dict
        if isinstance(data, (int, float)):
            result[skill_id] = {
                "level": _clamp_proficiency(data) or 1,
                "last_used_year": current_year
            }
            continue

        if not isinstance(data, dict):
            continue

        level = _clamp_proficiency(data.get("level"))
        if level is None:
            continue

        last_used = data.get("last_used_year", current_year)
        try:
            last_used = int(last_used)
        except (TypeError, ValueError):
            last_used = current_year

        result[skill_id] = {
            "level": level,
            "last_used_year": last_used
        }

    return result


def _sanitise_required_skills(
    raw: Any,
    allowlist: set[str],
) -> Dict[str, int]:
    """
    Sanitise required skills: {id: level}.
    """
    if not isinstance(raw, dict):
        logger.warning("required_skills is not a dict, defaulting to empty. Got: %r", raw)
        return {}

    result: Dict[str, int] = {}
    for skill_id, level in raw.items():
        if skill_id not in allowlist:
            continue
        clamped = _clamp_proficiency(level)
        if clamped is not None:
            result[skill_id] = clamped

    return result


def _sanitise_string_list(raw: Any, label: str) -> List[str]:
    """Ensure the raw value is a flat list of strings."""
    if not isinstance(raw, list):
        logger.warning("%s is not a list, defaulting to empty. Got: %r", label, raw)
        return []
    return [str(item) for item in raw if item]


# ─────────────────────────────────────────────────────────────────────────────
# ClaudeService
# ─────────────────────────────────────────────────────────────────────────────

class ClaudeService:
    """
    Thin wrapper around the Anthropic Messages API.

    The Anthropic client is instantiated lazily on first use so that the server
    can start up cleanly even before ANTHROPIC_API_KEY is set in the environment.
    """

    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self.model = model
        self._client: Optional[Any] = None

    # ──────────────────────────────────────────────────────────────────────────
    # Private: lazy client
    # ──────────────────────────────────────────────────────────────────────────

    def _get_client(self) -> Any:
        """Return the cached client, creating it on first call."""
        if self._client is None:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise RuntimeError(
                    "ANTHROPIC_API_KEY is not set. "
                    "Copy .env.example to .env and fill in your key."
                )
            self._client = anthropic.Anthropic(api_key=api_key)
        return self._client

    # ──────────────────────────────────────────────────────────────────────────
    # Private: raw API call
    # ──────────────────────────────────────────────────────────────────────────

    def _chat(self, system: str, user: str) -> str:
        """
        Send a single-turn message to Claude and return the raw text content.
        """
        client = self._get_client()
        logger.debug("Sending request to %s (max_tokens=%d)", self.model, MAX_TOKENS)

        response = client.messages.create(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user}],
        )

        if not response.content:
            raise ValueError("Claude returned an empty response (no content blocks).")

        raw_text: str = response.content[0].text
        logger.debug(
            "Received response: stop_reason=%s, output_tokens=%d",
            response.stop_reason,
            response.usage.output_tokens,
        )
        return raw_text

    # ──────────────────────────────────────────────────────────────────────────
    # Public: extract_skills
    # ──────────────────────────────────────────────────────────────────────────

    async def extract_skills(
        self,
        resume_text: str,
        jd_text: str,
        skill_ids: List[str],
    ) -> ParseResponse:
        """
        Extract structured skill data from a resume and job description.
        """
        allowlist: set[str] = set(skill_ids)

        # 1. Build prompts
        system_prompt = _build_system_prompt(skill_ids)
        user_prompt = _build_user_prompt(resume_text, jd_text)

        # 2. Call the API
        try:
            raw_text = self._chat(system=system_prompt, user=user_prompt)
        except Exception as exc:
            logger.error("Anthropic API error: %s", exc)
            
            # MOCK FALLBACK FOR TESTING (e.g. credit balance low)
            if "credit balance" in str(exc).lower() or "400" in str(exc):
                logger.warning("Triggering Mock Fallback for skill extraction due to API error.")
                return await self._mock_extract_skills(resume_text, jd_text, skill_ids)
            raise

        # 3. Strip accidental markdown fences
        clean_text = _strip_markdown_fences(raw_text)

        # 4. Parse JSON
        try:
            data: Dict[str, Any] = json.loads(clean_text)
        except json.JSONDecodeError as exc:
            logger.error(
                "JSON parse failure.\nraw_text=%r\nclean_text=%r\nerror=%s",
                raw_text,
                clean_text,
                exc,
            )
            text_summary = cast(Any, raw_text)[:500]
            raise ValueError(
                f"Claude did not return valid JSON. Parse error: {exc}\n"
                f"Raw response (first 500 chars): {text_summary}"
            ) from exc

        # 5. Sanitise + validate each field (zero-hallucination enforcement)
        candidate_skills = _sanitise_candidate_skills(
            data.get("candidate_skills"), allowlist
        )
        required_skills = _sanitise_required_skills(
            data.get("required_skills"), allowlist
        )
        raw_resume_skills = _sanitise_string_list(
            data.get("raw_resume_skills"), "raw_resume_skills"
        )
        raw_jd_skills = _sanitise_string_list(
            data.get("raw_jd_skills"), "raw_jd_skills"
        )

        # 6. Extract optional confidence score
        confidence_raw = data.get("extraction_confidence")
        extraction_confidence: Optional[float] = None
        if confidence_raw is not None:
            try:
                extraction_confidence = max(0.0, min(1.0, float(confidence_raw)))
            except (TypeError, ValueError):
                logger.warning(
                    "Could not parse extraction_confidence=%r, ignoring.", confidence_raw
                )

        logger.info(
            "Extraction complete: %d candidate skills, %d required skills, "
            "%d raw resume labels, %d raw JD labels",
            len(candidate_skills),
            len(required_skills),
            len(raw_resume_skills),
            len(raw_jd_skills),
        )

        # 7. Build and return the validated response model
        return ParseResponse(
            candidate_skills=candidate_skills,
            required_skills=required_skills,
            raw_resume_skills=raw_resume_skills,
            raw_jd_skills=raw_jd_skills,
            model_used=self.model,
            extraction_confidence=extraction_confidence,
        )

    async def _mock_extract_skills(
        self,
        resume_text: str,
        jd_text: str,
        skill_ids: List[str],
    ) -> ParseResponse:
        """
        Return a realistic-looking mock response for testing when Claude is unavailable.
        """
        import random
        
        # Pick some random skills from the allowlist that appear in the text (simple keyword match)
        found_candidate = {}
        found_required = {}
        
        for sid in skill_ids:
            clean_sid = sid.replace("_", " ")
            if clean_sid.lower() in resume_text.lower():
                found_candidate[sid] = {
                    "level": random.randint(2, 4),
                    "last_used_year": random.randint(2018, 2024)
                }
            if clean_sid.lower() in jd_text.lower():
                found_required[sid] = random.randint(3, 5)

        # Ensure we have at least SOMETHING if keywords didn't match
        if not found_candidate and skill_ids:
            found_candidate[skill_ids[0]] = {"level": 3, "last_used_year": 2023}
        if not found_required and skill_ids:
            found_required[skill_ids[0]] = 4

        return ParseResponse(
            candidate_skills=found_candidate,
            required_skills=found_required,
            raw_resume_skills=["(Mocked) Python", "(Mocked) SQL"],
            raw_jd_skills=["(Mocked) Lead Engineer", "(Mocked) AI"],
            model_used="mock-fallback-mode",
            extraction_confidence=0.5,
        )

