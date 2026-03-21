"""
groq_service.py – Groq Llama extraction for NexusLearn skill landscape.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, cast

import groq  # type: ignore
from models.schemas import ParseResponse  # type: ignore

logger = logging.getLogger(__name__)

# Constants
DEFAULT_MODEL = "llama-3.3-70b-versatile"
MAX_TOKENS = 4096
PROFICIENCY_MIN = 1
PROFICIENCY_MAX = 5

# Prompt logic inherited from LLM design patterns
def _build_system_prompt(skill_ids: List[str]) -> str:
    skill_list_str = "\n".join(f'  - "{s}"' for s in skill_ids)
    return f"""\
You are NexusLearn's Skill Extraction Engine. Analyse a candidate's resume and a JD, then return a structured JSON object.

PROFICIENCY SCALE:
1=Awareness, 2=Beginner, 3=Intermediate, 4=Advanced, 5=Expert

VALID SKILL IDs:
{skill_list_str}

OUTPUT RULES:
• Output ONLY valid JSON — no markdown fences, no preamble.
• Every key in candidate_skills and required_skills must be one of the valid skill IDs.
• Proficiency values must be integers 1–5.
• Output pure JSON, no explanation.

REQUIRED JSON SCHEMA:
{{
  "candidate_skills": {{
    "<skill_id>": {{ "level": <int 1-5>, "last_used_year": <int> }},
    ...
  }},
  "required_skills": {{
    "<skill_id>": <int 1-5>,
    ...
  }},
  "raw_resume_skills": ["<English label>", ...],
  "raw_jd_skills":     ["<English label>", ...],
  "extraction_confidence": <float 0.0-1.0>
}}"""

def _build_user_prompt(resume_text: str, jd_text: str) -> str:
    return f"RESUME:\n{resume_text}\n\nJD:\n{jd_text}\n\nExtracted Skills JSON:"

def _strip_markdown_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()

def _clamp_proficiency(value: Any) -> Optional[int]:
    try:
        v = int(value)
        return max(PROFICIENCY_MIN, min(PROFICIENCY_MAX, v))
    except (TypeError, ValueError):
        return None

def _sanitise_candidate_skills(raw: Any, allowlist: set[str], current_year: int = 2026) -> Dict[str, Dict[str, int]]:
    if not isinstance(raw, dict): return {}
    result: Dict[str, Dict[str, int]] = {}
    for skill_id, data in raw.items():
        if skill_id not in allowlist: continue
        if isinstance(data, (int, float)):
            result[skill_id] = {"level": _clamp_proficiency(data) or 1, "last_used_year": current_year}
            continue
        if not isinstance(data, dict): continue
        level = _clamp_proficiency(data.get("level"))
        if level is None: continue
        try:
            last_used = int(data.get("last_used_year", current_year))
        except (TypeError, ValueError):
            last_used = current_year
        result[skill_id] = {"level": level, "last_used_year": last_used}
    return result

def _sanitise_required_skills(raw: Any, allowlist: set[str]) -> Dict[str, int]:
    if not isinstance(raw, dict): return {}
    result: Dict[str, int] = {}
    for skill_id, level in raw.items():
        if skill_id in allowlist:
            clamped = _clamp_proficiency(level)
            if clamped is not None: result[skill_id] = clamped
    return result

def _sanitise_string_list(raw: Any) -> List[str]:
    if not isinstance(raw, list): return []
    return [str(item) for item in raw if item]

class GroqService:
    def __init__(self, model: str = DEFAULT_MODEL) -> None:
        self.model = model
        self._client: Optional[groq.Groq] = None

    def _get_client(self) -> groq.Groq:
        if self._client is None:
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                raise RuntimeError("GROQ_API_KEY not set in environment.")
            self._client = groq.Groq(api_key=api_key)
        return self._client

    async def extract_skills(self, resume_text: str, jd_text: str, skill_ids: List[str]) -> ParseResponse:
        allowlist = set(skill_ids)
        client = self._get_client()
        system_p = _build_system_prompt(skill_ids)
        user_p = _build_user_prompt(resume_text, jd_text)

        try:
            completion = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_p},
                    {"role": "user", "content": user_p}
                ],
                temperature=0.1,
                max_tokens=MAX_TOKENS,
                response_format={"type": "json_object"}
            )
            raw_text = completion.choices[0].message.content
        except Exception as exc:
            logger.error("Groq API error: %s", exc)
            if "not set" not in str(exc).lower():
                # Potential fallback if key is present but failing
                logger.warning("Groq extraction failed, check API key/credits.")
            raise

        data = json.loads(_strip_markdown_fences(raw_text))
        
        return ParseResponse(
            candidate_skills=_sanitise_candidate_skills(data.get("candidate_skills"), allowlist),
            required_skills=_sanitise_required_skills(data.get("required_skills"), allowlist),
            raw_resume_skills=_sanitise_string_list(data.get("raw_resume_skills")),
            raw_jd_skills=_sanitise_string_list(data.get("raw_jd_skills")),
            model_used=f"groq-{self.model}",
            extraction_confidence=data.get("extraction_confidence", 0.9)
        )

    async def generate_reasoning_traces(
        self,
        course_ids: List[str],
        gaps: Dict[str, Any],
        candidate_skills: Dict[str, int],
        course_skill_map: Optional[Dict[str, List[str]]] = None,
    ) -> Dict[str, str]:
        """
        Generate a rich, data-grounded reasoning for each course in the pathway.

        Parameters
        ----------
        course_ids:
            Ordered list of course IDs in the pathway.
        gaps:
            Dict of skill_id → {current, required, delta} from the gap engine.
        candidate_skills:
            Dict of skill_id → current proficiency level.
        course_skill_map:
            Optional dict of course_id → list of skill_ids the course teaches.
            When provided, each course gets a focused, skill-specific context rather
            than the full undifferentiated gap map. This produces much more specific traces.
        """
        if not course_ids:
            return {}
        client = self._get_client()

        # Build per-course focused context: only include the gaps that THIS course teaches.
        # This is the key fix — Groq now knows exactly which skills each course addresses,
        # enabling it to write genuinely course-specific traces.
        per_course_context: Dict[str, Any] = {}
        for cid in course_ids:
            taught_skills = (course_skill_map or {}).get(cid, [])
            if taught_skills:
                # Focused context: only the skills this course teaches
                course_gaps = {
                    sid: {
                        "current_level": candidate_skills.get(sid, 0),
                        "required_level": gaps[sid].get("required", 1) if isinstance(gaps.get(sid), dict) else 1,
                        "delta": gaps[sid].get("delta", 1) if isinstance(gaps.get(sid), dict) else 1,
                    }
                    for sid in taught_skills
                    if sid in gaps
                }
                per_course_context[cid] = {
                    "teaches_skills": taught_skills,
                    "gaps_addressed": course_gaps,
                }
            else:
                # Fallback: no mapping available, use full gap context
                per_course_context[cid] = {
                    "teaches_skills": [],
                    "gaps_addressed": {
                        sid: {
                            "current_level": candidate_skills.get(sid, 0),
                            "required_level": gaps[sid].get("required", 1) if isinstance(gaps.get(sid), dict) else 1,
                            "delta": gaps[sid].get("delta", 1) if isinstance(gaps.get(sid), dict) else 1,
                        }
                        for sid, gap_detail in gaps.items()
                        if isinstance(sid, str)
                    },
                }

        prompt = f"""
You are NexusLearn's AI reasoning engine. For each course in a personalised learning pathway,
write a single, specific, data-grounded sentence explaining exactly WHY this course was chosen
for THIS particular candidate.

RULES:
- For each course, you are given EXACTLY which skills it teaches and the candidate's current vs required level.
- Reference the specific skill name(s), the current level, and the target level (e.g. "you're at Level 1 in pandas, this course bridges the Δ3 gap to the required Level 4").
- If a course teaches a foundational skill, mention what advanced skill it UNLOCKS next in the pathway.
- Be direct, concrete, and specific. Never write a generic sentence that could apply to any course.
- Return ONLY a valid JSON object where keys are course IDs and values are ONE sentence strings.

Per-course context (course_id → teaches_skills + gaps_addressed with current/required/delta):
{json.dumps(per_course_context, indent=2)}

Candidate's overall skill levels: {json.dumps(candidate_skills)}
"""

        try:
            completion = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=2048,
                response_format={"type": "json_object"}
            )
            raw = completion.choices[0].message.content
            result = json.loads(_strip_markdown_fences(raw))
            # Ensure every course_id has a trace
            for cid in course_ids:
                if cid not in result:
                    result[cid] = f"Selected to address your identified skill gaps in the most efficient sequence."
            return result
        except Exception as exc:
            logger.error("Groq Reasoning Error: %s", exc)
            return {cid: "Strategic choice to address your primary skill gaps." for cid in course_ids}

    async def generate_custom_json(self, prompt: str) -> str:
        """
        Generic helper to get a JSON response from Groq for custom logic.
        """
        client = self._get_client()
        try:
            completion = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=MAX_TOKENS,
                response_format={"type": "json_object"}
            )
            return completion.choices[0].message.content
        except Exception as exc:
            logger.error("Groq Custom JSON error: %s", exc)
            return "{}"
