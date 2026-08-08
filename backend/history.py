"""
Reconstruct which past terms a student's completed courses were taken in.

The synthetic student profiles don't record when each course was taken. We
estimate a plausible chronology by distributing completed courses across
prior terms respecting prereqs, semester offerings, and credit caps.
"""
from __future__ import annotations

from typing import Any

from .models import Student
from .prerequisite_engine import PrerequisiteEngine


def _next_semester(term: str) -> str:
    season, year = term.split()
    y = int(year)
    if season == "Fall":
        return f"Spring {y + 1}"
    if season == "Spring":
        return f"Fall {y}"
    return f"Fall {y + 1}"


def _previous_semester(term: str) -> str:
    season, year = term.split()
    y = int(year)
    if season == "Fall":
        return f"Spring {y}"
    if season == "Spring":
        return f"Fall {y - 1}"
    return f"Spring {y}"


def reconstruct_history(student: Student, engine: PrerequisiteEngine) -> list[dict[str, Any]]:
    """Return list of {term, courses, total_credits, historical: True}."""
    completed = list(student.completed_courses)
    if not completed:
        return []
    cap = max(9, student.preferences.max_credits_per_semester)
    total_cr = sum(engine.courses[c].credits if c in engine.courses else 3 for c in completed)
    import math
    n_sems = max(1, math.ceil(total_cr / cap))

    start_term = student.current_semester
    for _ in range(n_sems):
        start_term = _previous_semester(start_term)

    plans: list[dict[str, Any]] = []
    placed: set[str] = set()
    remaining = list(completed)
    current_term = start_term
    max_iters = n_sems + 4

    for _ in range(max_iters):
        if not remaining:
            break
        season = current_term.split()[0].lower()

        def prereqs_met(cid: str) -> bool:
            course = engine.courses.get(cid)
            if course is None:
                return True
            for group in course.prerequisite_groups:
                # Group is satisfied if any option is placed OR outside completed set
                if not any(p in placed or p not in completed for p in group):
                    return False
            return True

        eligible = []
        for cid in remaining:
            course = engine.courses.get(cid)
            if course and course.semesters_offered:
                offered = [s.value for s in course.semesters_offered]
                if season not in offered:
                    continue
            if prereqs_met(cid):
                eligible.append(cid)

        def level_key(cid: str) -> int:
            c = engine.courses.get(cid)
            if c is None:
                return 1
            try:
                return int(c.level[0])
            except (ValueError, IndexError):
                return 1

        eligible.sort(key=level_key)

        picked: list[str] = []
        credits = 0.0
        for cid in eligible:
            cr = engine.courses[cid].credits if cid in engine.courses else 3
            if credits + cr > cap:
                continue
            picked.append(cid)
            credits += cr

        # Fallback: if nothing was placeable, force one to avoid deadlock
        if not picked and remaining:
            cid = remaining[0]
            picked.append(cid)
            credits = engine.courses[cid].credits if cid in engine.courses else 3

        plans.append({
            "term": current_term,
            "courses": picked,
            "total_credits": credits,
            "historical": True,
        })
        placed.update(picked)
        remaining = [c for c in remaining if c not in picked]
        current_term = _next_semester(current_term)

    return plans
