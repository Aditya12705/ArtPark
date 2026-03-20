"""
pathway_builder.py – Pure-Python learning pathway construction for PathForge.

No external graph libraries. All graph operations use dicts, sets, and deques.

──────────────────────────────────────────────────────────────────────────────
Algorithm overview (for the README)
──────────────────────────────────────────────────────────────────────────────

build_pathway  (pure Python, deterministic)
──────────────
1. FILTER
   Retain only catalog courses that teach ≥ 1 gap skill.
   Courses teaching exclusively competent skills are excluded here; they are
   separately captured by identify_skipped_courses for UI transparency.

2. DEPENDENCY GRAPH
   For each retained course C, look at its "requires" field (prerequisite
   skill IDs). Any OTHER retained course D that teaches a skill in C.requires
   creates an edge  D → C  ("D must come before C").
   This builds a directed graph over courses (not skills) whose edges encode
   the skill-level prerequisite ordering.

3. KAHN'S ALGORITHM  (BFS topological sort)
   Standard Kahn's:
     a. Compute in-degree for every course node.
     b. Enqueue all nodes with in-degree = 0 (no prerequisites to satisfy first).
     c. While the queue is non-empty:
          Pop a set of nodes that are all at the current "level" (frontier).
          Sort the frontier by priority score (step 4) before appending.
          Emit each node in priority order.
          Decrement in-degrees of successors; enqueue any that reach 0.
   If the sub-graph has a cycle (bad catalog data), unprocessed nodes are
   appended at the end with a warning — the algorithm never blocks.

4. TIE-BREAKING  (same topological level)
   Among courses with the same in-degree at a given BFS step, rank by:
     priority_score = Σ gap.delta for each skill the course teaches
   Higher total delta ↓ first — addresses the biggest skill deficiencies first.

generate_reasoning_traces  (single LLM call)
──────────────────────────
Calls Claude once with:
  • The ordered course list (ids + titles)
  • Each course's gap skills with their delta values (grounded in real numbers)
  • The candidate's current and required levels per skill
Asks for exactly one sentence per course referencing specific skill names and
delta values.  Response is parsed as JSON → dict[course_id, reason].

identify_skipped_courses  (pure Python, zero LLM)
────────────────────────
Returns catalog courses not selected by build_pathway because every skill
they teach is in already_competent.  Surfaced in the UI as "already done".
──────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import json
import logging
import os
import re
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Set, Tuple

from models.schemas import GapResponse, SkillGapDetail

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Internal types
# ─────────────────────────────────────────────────────────────────────────────

# A course dict as loaded from course_catalog.yaml
CourseDef = Dict[str, Any]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _course_id(course: CourseDef) -> str:
    return course["id"]


def _taught_skills(course: CourseDef) -> List[str]:
    """Return the skill IDs this course teaches (field: 'teaches')."""
    return course.get("teaches", course.get("covers_skills", []))


def _required_skills(course: CourseDef) -> List[str]:
    """Return prerequisite skill IDs for this course (field: 'requires')."""
    return course.get("requires", course.get("prerequisites", []))


def _priority_score(course: CourseDef, gaps: Dict[str, SkillGapDetail]) -> int:
    """
    Priority score = sum of gap deltas across all skills this course teaches.
    Higher → course addresses bigger capability deficiencies → ranked first.
    """
    return sum(
        gaps[sid].delta
        for sid in _taught_skills(course)
        if sid in gaps
    )


def _strip_fences(text: str) -> str:
    """Remove accidental ```json ... ``` wrapping from Claude's output."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 – Filter catalog
# ─────────────────────────────────────────────────────────────────────────────

def _filter_relevant_courses(
    course_catalog: List[CourseDef],
    gap_skill_ids: Set[str],
) -> List[CourseDef]:
    """
    Keep only courses that teach ≥ 1 gap skill.

    Strict catalog grounding: a course must exist verbatim in the catalog to
    appear in the output — the builder never synthesises courses.
    """
    relevant = [
        c for c in course_catalog
        if any(sid in gap_skill_ids for sid in _taught_skills(c))
    ]
    logger.debug(
        "Catalog filter: %d/%d courses retained for gap skills %s",
        len(relevant), len(course_catalog), sorted(gap_skill_ids),
    )
    return relevant


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 – Build course dependency graph
# ─────────────────────────────────────────────────────────────────────────────

def _build_course_graph(
    courses: List[CourseDef],
) -> Tuple[Dict[str, Set[str]], Dict[str, int]]:
    """
    Build a directed graph over courses derived from skill-level prerequisites.

    Edge semantics:  provider_id → consumer_id
    ("provider must be completed before consumer")

    An edge D → C exists when:
        C.requires contains a skill S  AND  D.teaches contains S
        AND D ≠ C

    Returns
    -------
    adjacency : dict[course_id, set[successor_ids]]
    in_degree : dict[course_id, int]
    """
    # Map skill_id → set of courses that teach it
    skill_to_courses: Dict[str, Set[str]] = defaultdict(set)
    for course in courses:
        for sid in _taught_skills(course):
            skill_to_courses[sid].add(_course_id(course))

    all_ids: Set[str] = {_course_id(c) for c in courses}
    adjacency: Dict[str, Set[str]] = {cid: set() for cid in all_ids}
    in_degree: Dict[str, int] = {cid: 0 for cid in all_ids}

    for course in courses:
        consumer_id = _course_id(course)
        for req_skill in _required_skills(course):
            # Every course that teaches req_skill becomes a provider of consumer
            for provider_id in skill_to_courses.get(req_skill, set()):
                if provider_id == consumer_id:
                    continue  # self-loop guard
                if consumer_id not in adjacency[provider_id]:
                    adjacency[provider_id].add(consumer_id)
                    in_degree[consumer_id] += 1
                    logger.debug(
                        "  Edge: %s → %s  (via skill '%s')",
                        provider_id, consumer_id, req_skill,
                    )

    return adjacency, in_degree


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 & 4 – Kahn's algorithm with priority-aware tie-breaking
# ─────────────────────────────────────────────────────────────────────────────

def _kahn_sort(
    courses: List[CourseDef],
    adjacency: Dict[str, Set[str]],
    in_degree: Dict[str, int],
    gaps: Dict[str, SkillGapDetail],
) -> List[str]:
    """
    Topological sort via Kahn's BFS algorithm with priority-based tie-breaking.

    Tie-breaking rule (same topological level):
        Sort by priority_score = Σ gap.delta of taught skills (descending).
        Courses that address larger deficiencies are scheduled first.

    Cycle handling:
        If the catalog data contains a cycle, the remaining unvisited nodes are
        appended after the sorted prefix with a warning (degrade gracefully).

    Returns
    -------
    List[str]  – ordered course IDs, dependency-safe.
    """
    id_to_course: Dict[str, CourseDef] = {_course_id(c): c for c in courses}

    # Working copies so we don't mutate the caller's structures
    in_deg: Dict[str, int] = dict(in_degree)

    # Initialise frontier: all courses with no prerequisites in the subgraph
    # Sort the initial frontier by priority score (highest first)
    frontier_ids = [cid for cid, deg in in_deg.items() if deg == 0]
    frontier_ids.sort(
        key=lambda cid: _priority_score(id_to_course[cid], gaps),
        reverse=True,
    )
    queue: deque[str] = deque(frontier_ids)

    ordered: List[str] = []
    visited: Set[str] = set()

    while queue:
        # Drain the entire current frontier as a "level"
        level_batch: List[str] = []
        # Snapshot current queue length to process only this level atomically
        level_size = len(queue)
        for _ in range(level_size):
            cid = queue.popleft()
            level_batch.append(cid)
            visited.add(cid)

        # Sort the level by priority score (tie-break: highest delta sum first)
        level_batch.sort(
            key=lambda cid: _priority_score(id_to_course[cid], gaps),
            reverse=True,
        )
        ordered.extend(level_batch)

        # Expand successors for every node in this level
        next_frontier: List[str] = []
        for cid in level_batch:
            for successor in adjacency.get(cid, set()):
                in_deg[successor] -= 1
                if in_deg[successor] == 0:
                    next_frontier.append(successor)

        # Sort next frontier immediately so the deque stays priority-ordered
        next_frontier.sort(
            key=lambda cid: _priority_score(id_to_course[cid], gaps),
            reverse=True,
        )
        queue.extend(next_frontier)

    # Cycle detection: any unvisited nodes indicate a cycle in catalog data
    unvisited = [cid for cid in in_deg if cid not in visited]
    if unvisited:
        logger.warning(
            "Cycle detected in course dependency graph! "
            "Appending %d unresolvable course(s) at the end: %s",
            len(unvisited), unvisited,
        )
        ordered.extend(unvisited)

    return ordered


# ─────────────────────────────────────────────────────────────────────────────
# Public: build_pathway
# ─────────────────────────────────────────────────────────────────────────────

def build_pathway(
    gaps: GapResponse,
    course_catalog: List[CourseDef],
    skills_graph: Dict[str, dict],
    max_courses: Optional[int] = None,
) -> List[str]:
    """
    Build an ordered, dependency-safe learning pathway for the given gap profile.

    Parameters
    ----------
    gaps:
        GapResponse from gap_engine.compute — contains the gaps dict, already_competent,
        missing_entirely, and total_gap_score.
    course_catalog:
        Full list of course dicts loaded from course_catalog.yaml.
    skills_graph:
        Full skill DAG loaded from skills_graph.json (currently reserved for
        future cross-referencing; the course graph is built from catalog metadata).
    max_courses:
        Optional cap on the number of courses returned.  If None, all are returned.

    Returns
    -------
    list[str]
        Ordered course IDs: a student following them in sequence will always
        satisfy prerequisites before encountering courses that need them.
    """
    if not gaps.gaps:
        logger.info("No gaps to address — pathway is empty.")
        return []

    gap_skill_ids: Set[str] = set(gaps.gaps.keys())

    # Step 1: filter
    relevant = _filter_relevant_courses(course_catalog, gap_skill_ids)
    if not relevant:
        logger.warning("No catalog courses teach any of the gap skills: %s", gap_skill_ids)
        return []

    # Step 2: dependency graph
    adjacency, in_degree = _build_course_graph(relevant)

    # Step 3 & 4: topological sort with priority tie-breaking
    ordered_ids = _kahn_sort(
        courses=relevant,
        adjacency=adjacency,
        in_degree=in_degree,
        gaps=gaps.gaps,
    )

    if max_courses is not None:
        ordered_ids = ordered_ids[:max_courses]

    logger.info(
        "Pathway built: %d course(s) ordered for %d gap skill(s).",
        len(ordered_ids), len(gap_skill_ids),
    )
    return ordered_ids


# ─────────────────────────────────────────────────────────────────────────────
# Public: identify_skipped_courses
# ─────────────────────────────────────────────────────────────────────────────

def identify_skipped_courses(
    course_catalog: List[CourseDef],
    gaps: GapResponse,
    already_competent: List[str],
) -> List[str]:
    """
    Return course IDs that are skipped because the candidate is already competent
    in ALL skills those courses teach.

    A course is skipped when:
        every skill in course.teaches is in already_competent
        AND none of those skills is in gaps.gaps

    These are surfaced in the UI as "you already know this" so the candidate
    feels recognised for their existing expertise.

    Parameters
    ----------
    course_catalog:
        Full course list from course_catalog.yaml.
    gaps:
        GapResponse containing the current gaps dict and already_competent list.
    already_competent:
        List of skill IDs the candidate fully satisfies (from GapResponse).

    Returns
    -------
    list[str]  – course IDs (not titles) of skipped courses, alphabetically sorted.
    """
    competent_set: Set[str] = set(already_competent)
    gap_skill_set: Set[str] = set(gaps.gaps.keys())

    skipped: List[str] = []
    for course in course_catalog:
        taught = set(_taught_skills(course))
        if not taught:
            continue
        # All taught skills are competent AND none are gaps → skip
        if taught.issubset(competent_set) and taught.isdisjoint(gap_skill_set):
            skipped.append(_course_id(course))
            logger.debug(
                "Skipped course '%s' — all taught skills already competent: %s",
                _course_id(course), sorted(taught),
            )

    logger.info("Identified %d skipped course(s).", len(skipped))
    return sorted(skipped)


# ─────────────────────────────────────────────────────────────────────────────
# Public: generate_reasoning_traces  (single Claude call)
# ─────────────────────────────────────────────────────────────────────────────

async def generate_reasoning_traces(
    ordered_course_ids: List[str],
    gaps: GapResponse,
    candidate_skills: Dict[str, int],
    course_catalog: List[CourseDef],
    skills_graph: Dict[str, dict],
) -> Dict[str, str]:
    """
    Call Claude once to generate a one-sentence personalised reason for each
    recommended course.  Each reason must reference the candidate's actual
    skill levels and delta values — no generic explanations.

    Parameters
    ----------
    ordered_course_ids:
        The output of build_pathway (course IDs in recommended sequence).
    gaps:
        GapResponse with skill-level delta information.
    candidate_skills:
        Map of skill_id → current proficiency (for grounding reasons in real numbers).
    course_catalog:
        Full course list (used to look up titles and taught skills).
    skills_graph:
        Skill DAG (used to look up skill names from IDs).

    Returns
    -------
    dict[course_id, reasoning_sentence]
        One entry per ordered course.  Falls back to a templated string if the
        Claude call fails, so the endpoint always returns a usable payload.
    """
    # Always import here to avoid circular imports at module level
    import anthropic  # noqa: PLC0415

    if not ordered_course_ids:
        return {}

    # ── Lookup tables ───────────────────────────────────────────────────────
    id_to_course: Dict[str, CourseDef] = {_course_id(c): c for c in course_catalog}
    skill_names: Dict[str, str] = {
        sid: node.get("name", sid.replace("_", " ").title())
        for sid, node in skills_graph.items()
    }

    # ── Build a compact, grounded context block ──────────────────────────────
    course_context_lines: List[str] = []
    for idx, cid in enumerate(ordered_course_ids, start=1):
        course = id_to_course.get(cid)
        if not course:
            continue
        title = course.get("title", cid)
        taught = _taught_skills(course)

        skill_details: List[str] = []
        for sid in taught:
            name = skill_names.get(sid, sid)
            gap_detail = gaps.gaps.get(sid)
            if gap_detail:
                skill_details.append(
                    f"{name} [current={gap_detail.current}, "
                    f"required={gap_detail.required}, delta={gap_detail.delta}]"
                )
            elif sid in gaps.already_competent:
                current = candidate_skills.get(sid, 0)
                skill_details.append(f"{name} [already competent at level {current}]")

        skills_str = "; ".join(skill_details) if skill_details else "general skills"
        course_context_lines.append(
            f'{idx}. course_id="{cid}" title="{title}" teaches=[{skills_str}]'
        )

    context_block = "\n".join(course_context_lines)

    # ── Prompts ──────────────────────────────────────────────────────────────
    system_prompt = """\
You are PathForge's learning pathway explainer. Your job is to write exactly ONE \
sentence per course explaining why that specific course is recommended for THIS \
candidate, based on their actual skill gaps.

Rules:
• Reference the specific skill name(s) and the delta value(s) in your reason.
• Never write a generic description like "this course teaches Python".
• Always personalise: "You currently have X but need Y, so..."
• Be concise: one sentence, 20–40 words max per course.
• Output ONLY a valid JSON object mapping course_id → reason string.
• No markdown fences, no preamble, no trailing text.

Output schema:
{
  "<course_id>": "<one-sentence personalised reason>",
  ...
}"""

    user_prompt = f"""\
The candidate's recommended learning pathway (in order):

{context_block}

Write exactly one personalised sentence per course explaining why it was chosen \
for this candidate. Reference the actual skill names and delta values shown above."""

    # ── Call Claude ──────────────────────────────────────────────────────────
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set — using templated fallback reasoning.")
        return _fallback_traces(ordered_course_ids, id_to_course, gaps, skill_names)

    model = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-5")

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw_text = response.content[0].text
        clean = _strip_fences(raw_text)
        traces: Dict[str, str] = json.loads(clean)

        # Discard any course IDs Claude invented that aren't in our ordered list
        valid_ids = set(ordered_course_ids)
        traces = {k: v for k, v in traces.items() if k in valid_ids}

        # Fill in any missing courses with the templated fallback
        for cid in ordered_course_ids:
            if cid not in traces:
                logger.warning("Claude omitted reasoning for course '%s' — using fallback.", cid)
                traces[cid] = _single_fallback(cid, id_to_course, gaps, skill_names)

        logger.info(
            "Reasoning traces generated by %s for %d course(s).",
            model, len(traces),
        )
        return traces

    except (anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
        logger.error("Claude API error during reasoning trace generation: %s", exc)
        return _fallback_traces(ordered_course_ids, id_to_course, gaps, skill_names)
    except (json.JSONDecodeError, KeyError, IndexError) as exc:
        logger.error("Failed to parse Claude reasoning response: %s", exc)
        return _fallback_traces(ordered_course_ids, id_to_course, gaps, skill_names)


# ─────────────────────────────────────────────────────────────────────────────
# Fallback reasoning (no LLM, template-based)
# ─────────────────────────────────────────────────────────────────────────────

def _single_fallback(
    course_id: str,
    id_to_course: Dict[str, CourseDef],
    gaps: GapResponse,
    skill_names: Dict[str, str],
) -> str:
    """Generate a template-based reason for a single course."""
    course = id_to_course.get(course_id, {})
    title = course.get("title", course_id)
    taught_gap_skills = [
        sid for sid in _taught_skills(course) if sid in gaps.gaps
    ]
    if taught_gap_skills:
        details = ", ".join(
            f"{skill_names.get(s, s)} (Δ{gaps.gaps[s].delta})"
            for s in taught_gap_skills[:3]
        )
        return (
            f"'{title}' is recommended to close your gap(s) in {details}."
        )
    return f"'{title}' supports skills relevant to your target role."


def _fallback_traces(
    ordered_course_ids: List[str],
    id_to_course: Dict[str, CourseDef],
    gaps: GapResponse,
    skill_names: Dict[str, str],
) -> Dict[str, str]:
    """Generate templated fallback reasoning for all courses."""
    return {
        cid: _single_fallback(cid, id_to_course, gaps, skill_names)
        for cid in ordered_course_ids
    }


# ─────────────────────────────────────────────────────────────────────────────
# Convenience class – used by the /pathway router
# ─────────────────────────────────────────────────────────────────────────────

class PathwayBuilder:
    """
    Stateless service class wrapping all pathway-construction functions.

    The course catalog and skills graph are injected at construction time so
    expensive file I/O happens once at startup, not per-request.
    """

    def __init__(
        self,
        course_catalog: List[CourseDef],
        skills_graph: Dict[str, dict],
    ) -> None:
        self.course_catalog = course_catalog
        self.skills_graph = skills_graph

    async def build(
        self,
        gaps: GapResponse,
        candidate_skills: Dict[str, int],
        already_competent: List[str],
        max_courses: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Full pathway pipeline:
        1. Build ordered course list (pure Python, deterministic).
        2. Identify skipped courses.
        3. Generate per-course reasoning traces (single Claude call).

        Returns a dict ready to be unpacked into PathwayResponse.
        """
        # 1. Topological pathway
        ordered_ids = build_pathway(
            gaps=gaps,
            course_catalog=self.course_catalog,
            skills_graph=self.skills_graph,
            max_courses=max_courses,
        )

        # 2. Skipped courses
        skipped = identify_skipped_courses(
            course_catalog=self.course_catalog,
            gaps=gaps,
            already_competent=already_competent,
        )

        # 3. Reasoning traces (Claude, with graceful fallback)
        traces = await generate_reasoning_traces(
            ordered_course_ids=ordered_ids,
            gaps=gaps,
            candidate_skills=candidate_skills,
            course_catalog=self.course_catalog,
            skills_graph=self.skills_graph,
        )

        # 4. Assemble course recommendation dicts
        id_to_course = {_course_id(c): c for c in self.course_catalog}
        recommendations = []
        total_hours = 0
        for cid in ordered_ids:
            c = id_to_course.get(cid, {})
            hours = float(c.get("duration_hours", 0))
            total_hours += hours
            recommendations.append({
                "course_id": cid,
                "title": c.get("title", cid),
                "duration_hours": hours,
                "level": c.get("level", "beginner"),
                "skills_addressed": _taught_skills(c),
                "reasoning": traces.get(cid, ""),
            })

        return {
            "pathway": recommendations,
            "skipped_courses": skipped,
            "estimated_total_hours": round(total_hours),
            "reasoning_traces": traces,
        }
