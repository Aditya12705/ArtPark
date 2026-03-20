import sys
import os

# Add backend directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.dirname(current_dir)
sys.path.append(backend_dir)

from services.gap_engine import apply_skill_decay, compute_gap  # type: ignore
from services.pathway_builder import PathwayBuilder         # type: ignore
import asyncio
from models.schemas import GapResponse, SkillGapDetail    # type: ignore

def test_skill_decay():
    print("Testing Temporal Skill Decay...")
    # Skill used in 2024 (2 years ago from 2026)
    skills = {"python": {"level": 4, "last_used_year": 2024}}
    decayed = apply_skill_decay(skills, current_year=2026)
    # 2 years idle * 0.5 = 1 penalty. 4 - 1 = 3.
    assert decayed["python"] == 3
    print("  [PASS] Skill decay applied correctly")

    # Skill used in 2020 (6 years ago)
    skills = {"java": {"level": 5, "last_used_year": 2020}}
    decayed = apply_skill_decay(skills, current_year=2026)
    # 6 years idle * 0.5 = 3 penalty. 5 - 3 = 2.
    assert decayed["java"] == 2
    print("  [PASS] Skill decay applied correctly")

def test_cognitive_load_balancing():
    print("Testing Cognitive Load Balancing...")
    # Mock data
    gaps = GapResponse(
        gaps={
            "python": SkillGapDetail(current=1, required=4, delta=3),
            "soft_skills": SkillGapDetail(current=2, required=3, delta=1)
        },
        already_competent=[],
        missing_entirely=[],
        total_gap_score=4
    )
    
    catalog = [
        {
            "id": "course_python_heavy",
            "title": "Advanced Python",
            "teaches": ["python"],
            "cognitive_load": "high",
            "duration_hours": 10
        },
        {
            "id": "course_soft_easy",
            "title": "Team Communication",
            "teaches": ["soft_skills"],
            "cognitive_load": "low",
            "duration_hours": 2
        }
    ]
    
    # First course in pathway should be the one with highest delta if no previous load
    # But if we force the first step to be after a "high" load (mocking the loop),
    # we want to see if it prioritizes the "low" load one.
    
    # We'll test the builder's sorting logic by looking at the order
    builder = PathwayBuilder(catalog, {})
    result = asyncio.run(builder.build(gaps, {}, []))
    ordered = [c["id"] for c in result["pathway"]]
    
    # Without load balancing history, "python" (delta 3) should come before "soft_skills" (delta 1)
    assert ordered[0] == "course_python_heavy"
    print("  [PASS] Basic priority sorting works")

def test_time_budget():
    print("Testing HR Time Budget...")
    gaps = GapResponse(
        gaps={
            "s1": SkillGapDetail(current=0, required=1, delta=1),
            "s2": SkillGapDetail(current=0, required=1, delta=1),
            "s3": SkillGapDetail(current=0, required=1, delta=1)
        },
        already_competent=[],
        missing_entirely=[],
        total_gap_score=3
    )
    catalog = [
        {"id": "c1", "teaches": ["s1"], "duration_hours": 10},
        {"id": "c2", "teaches": ["s2"], "duration_hours": 10},
        {"id": "c3", "teaches": ["s3"], "duration_hours": 10}
    ]
    
    # 25 hour budget: should fit exactly 2 courses
    builder = PathwayBuilder(catalog, {})
    result = asyncio.run(builder.build(gaps, {}, [], max_hours=25))
    ordered = [c["id"] for c in result["pathway"]]
    assert len(ordered) == 2, f"Expected 2 courses, got {len(ordered)}: {ordered}"
    print("  [PASS] Time budget constraint works")

if __name__ == "__main__":
    try:
        test_skill_decay()
        test_cognitive_load_balancing()
        test_time_budget()
        print("\nAll algorithmic feature verifications passed!")
    except Exception as e:
        print(f"\nVerification FAILED: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
