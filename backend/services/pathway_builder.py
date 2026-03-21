"""
pathway_builder.py – Pure-Python learning pathway construction for NexusLearn.
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Set, Tuple, cast

from models.schemas import GapResponse, SkillGapDetail  # type: ignore

logger = logging.getLogger(__name__)

CourseDef = Dict[str, Any]

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _course_id(course: CourseDef) -> str:
    return course["id"]

def _taught_skills(course: CourseDef) -> List[str]:
    raw = course.get("teaches", course.get("covers_skills", []))
    return cast(List[str], raw)

def _required_skills(course: CourseDef) -> List[str]:
    raw = course.get("requires", course.get("prerequisites", []))
    return cast(List[str], raw)

def _priority_score(course: CourseDef, gaps: Dict[str, SkillGapDetail]) -> int:
    return sum(
        gaps[sid].delta  # type: ignore
        for sid in _taught_skills(course)
        if sid in gaps
    )

def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()

# ─────────────────────────────────────────────────────────────────────────────
# PathwayBuilder Class
# ─────────────────────────────────────────────────────────────────────────────

class PathwayBuilder:
    def __init__(self, course_catalog: List[CourseDef], skills_graph: Dict[str, Any], groq_svc: Optional[Any] = None):
        self.course_catalog = course_catalog
        self.skills_graph = skills_graph
        self.groq_svc = groq_svc

    async def build(
        self,
        gaps: GapResponse,
        candidate_skills: Dict[str, int],
        already_competent: List[str],
        max_courses: Optional[int] = None,
        max_hours: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Orchestrate the full pathway generation pipeline.
        Returns a dict matching the PathwayResponse model.
        """
        # 1. Build the ordered IDs
        ordered_ids = self._get_ordered_ids(gaps, max_courses, max_hours)
        
        # 2. Identify skipped courses
        skipped = self._identify_skipped(gaps, already_competent)

        # 3. Identify Orphan Gaps (Gaps not addressed by selected courses)
        id_to_course = {c["id"]: c for c in self.course_catalog}
        addressed_skills = set()
        for cid in ordered_ids:
            if cid in id_to_course:
                addressed_skills.update(_taught_skills(id_to_course[cid]))
        
        orphan_gaps = {sid: detail for sid, detail in gaps.gaps.items() if sid not in addressed_skills}
        
        # 4. Use Groq to discover resources for orphan gaps if they exist
        discovery_courses = []
        if orphan_gaps and self.groq_svc:
            try:
                discovery_courses = await self._discover_resources(orphan_gaps)
            except Exception as exc:
                logger.error("Failed dynamic discovery: %s", exc)
        
        # 5. Assemble static-catalog details and track hours consumed
        pathway_details: List[Dict[str, Any]] = []
        total_hours: float = 0
        for cid in ordered_ids:
            course = id_to_course.get(cid)
            if course:
                pathway_details.append(course)
                total_hours += float(course.get("duration_hours") or 0)

        # 6. Add discovery courses ONLY if they fit within the remaining budget
        remaining_hours: Optional[float] = (
            float(max_hours) - total_hours if max_hours is not None else None
        )
        for dc in discovery_courses:
            dc_hours = float(dc.get("duration_hours") or 0)
            if remaining_hours is not None and dc_hours > remaining_hours:
                logger.info(
                    "Discovery course '%s' (%.0fh) skipped – exceeds remaining budget (%.0fh left).",
                    dc.get("id", "?"), dc_hours, remaining_hours,
                )
                continue
            pathway_details.append(dc)
            total_hours += dc_hours
            if remaining_hours is not None:
                remaining_hours -= dc_hours

        # 7. Generate reasoning traces for final pathway
        all_ids = [c["id"] for c in pathway_details]
        traces = await self._generate_traces(all_ids, gaps, candidate_skills)

        return {
            "pathway": pathway_details,
            "skipped_courses": skipped,
            "estimated_total_hours": int(total_hours),
            "reasoning_traces": traces
        }

    async def _discover_resources(self, orphan_gaps: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Ask Groq to suggest learning resources for skills not in our catalog.
        """
        if not self.groq_svc:
            return []
        
        gaps_info = {sid: {"delta": getattr(d, 'delta', 1) if not isinstance(d, dict) else d.get('delta', 1)} for sid, d in orphan_gaps.items()}
        prompt = f"""
        Our static course catalog is missing content for these specific skill gaps: {json.dumps(gaps_info)}
        For each skill, suggest ONE high-quality, free learning resource.
        Return a JSON object exactly like this:
        {{
          "discovery_pathway": [
            {{
              "id": "discovery_<skill_id>",
              "title": "Suggested: <Resource Title>",
              "provider": "AI DISCOVERY",
              "url": "<URL to the resource or a search query link>",
              "duration_hours": 5,
              "level": "intermediate",
              "cognitive_load": "medium",
              "teaches": ["<skill_id>"],
              "description": "Recommended by AI to bridge catalog gap."
            }}
          ]
        }}
        """
        try:
            raw = await self.groq_svc.generate_custom_json(prompt)
            data = json.loads(raw)
            if isinstance(data, dict) and "discovery_pathway" in data:
                return cast(List[Dict[str, Any]], data["discovery_pathway"])
            return []
        except Exception as exc:
            logger.error("Discovery error: %s", exc)
            return []

    def _get_ordered_ids(
        self,
        gaps: GapResponse,
        max_courses: Optional[int],
        max_hours: Optional[int]
    ) -> List[str]:
        if not gaps.gaps:
            return []

        gap_ids = set(gaps.gaps.keys())
        # Filter
        relevant = [
            c for c in self.course_catalog
            if any(sid in gap_ids for sid in _taught_skills(c))
        ]
        if not relevant:
            return []

        # Graph
        skill_to_courses = defaultdict(set)
        for c in relevant:
            for sid in _taught_skills(c):
                skill_to_courses[sid].add(c["id"])

        adj = {c["id"]: set() for c in relevant}
        in_deg = {c["id"]: 0 for c in relevant}
        id_to_course = {c["id"]: c for c in relevant}

        for c in relevant:
            cid = c["id"]
            for req in _required_skills(c):
                for p_id in skill_to_courses.get(req, set()):
                    if p_id != cid and cid not in adj[p_id]: # type: ignore
                        adj[p_id].add(cid) # type: ignore
                        in_deg[cid] += 1 # type: ignore

        # Kahn's with Cognitive Load Balancing
        # Use a mutable container so the priority closure sees an up-to-date last_load
        # even as courses are scheduled one-by-one within the same processing pass.
        state = {"last_load": "low"}

        def priority(cid_in: str) -> int:
            base = _priority_score(id_to_course[cid_in], gaps.gaps)
            load = id_to_course[cid_in].get("cognitive_load", "high")
            if state["last_load"] == "high" and load == "low":
                return base + 1000
            return base

        queue = deque(sorted([i for i in in_deg if in_deg[i] == 0], key=priority, reverse=True))
        ordered = []
        visited = set()

        while queue:
            # Re-sort available nodes each time so last_load is applied correctly
            available = sorted(list(queue), key=priority, reverse=True)
            queue.clear()
            queue.extend(available)
            cid = queue.popleft()
            ordered.append(cid)
            visited.add(cid)
            state["last_load"] = id_to_course[cid].get("cognitive_load", "high")
            for succ in adj.get(cid, set()): # type: ignore
                in_deg[succ] -= 1 # type: ignore
                if in_deg[succ] == 0:
                    queue.append(succ)

        # Budget caps
        if max_hours is not None:
            budgeted: List[str] = []
            cur_h: int = 0
            for cid in ordered:
                dur = int(id_to_course[cid].get("duration_hours", 0))
                if max_hours is not None and (int(cur_h) + int(dur)) <= int(max_hours):
                    budgeted.append(cid)
                    cur_h = int(cur_h) + int(dur)
            ordered = budgeted

        if max_courses is not None and len(ordered) > int(max_courses):
            # Casting ordered to list and int(max_courses) for slice safety
            ordered = list(ordered)[:int(max_courses)]

        return ordered

    def _identify_skipped(self, gaps: GapResponse, already_competent: List[str]) -> List[str]:
        comp_set = set(already_competent)
        gap_set = set(gaps.gaps.keys())
        skipped = []
        for c in self.course_catalog:
            taught = set(_taught_skills(c))
            if taught and taught.issubset(comp_set) and taught.isdisjoint(gap_set):
                skipped.append(c["id"])
        return sorted(skipped)

    async def _generate_traces(
        self,
        ids: List[str],
        gaps: GapResponse,
        candidate: Dict[str, int],
    ) -> Dict[str, str]:
        if not ids:
            return {}
        if self.groq_svc:
            try:
                # Serialize gap details for JSON transport
                serializable_gaps = {
                    sid: {"current": detail.current, "required": detail.required, "delta": detail.delta}
                    for sid, detail in gaps.gaps.items()
                }

                # Build course→skills map so Groq can write per-course-specific traces
                id_to_course = {c["id"]: c for c in self.course_catalog}
                course_skill_map: Dict[str, List[str]] = {
                    cid: _taught_skills(id_to_course[cid])
                    for cid in ids
                    if cid in id_to_course
                }

                return await self.groq_svc.generate_reasoning_traces(
                    ids,
                    serializable_gaps,
                    candidate,
                    course_skill_map=course_skill_map,
                )
            except Exception as exc:
                logger.error("Failed to generate Groq traces: %s", exc)

        # Fallback: generate a data-grounded trace from the gap data directly
        fallback: Dict[str, str] = {}
        id_to_course = {c["id"]: c for c in self.course_catalog}
        for cid in ids:
            course = id_to_course.get(cid)
            if course:
                taught = _taught_skills(course)
                addressed = [s for s in taught if s in gaps.gaps]
                if addressed:
                    s = addressed[0]
                    d = gaps.gaps[s]
                    name = s.replace("_", " ").title()
                    fallback[cid] = (
                        f"Bridges your Δ{d.delta} gap in {name} "
                        f"(current: Level {d.current} → required: Level {d.required})."
                    )
                else:
                    fallback[cid] = "Builds foundational competency required for downstream modules."
            else:
                fallback[cid] = "AI-suggested resource to bridge a catalog gap."
        return fallback
