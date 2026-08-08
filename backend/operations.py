"""
Operation validation and application engine.

This module enforces the same guardrails as the JS artifact:
  1. Course must exist in the catalog.
  2. Course must be in the student's program universe (no cross-program mixing).
  3. Move/remove: source course must actually be in the plan.
  4. Move/add: destination term must offer this course (season match).
  5. Move/add: prereqs must be satisfied by the destination term.
  6. Cannot modify past terms or current term — only planned future terms.

Preference operations (change_concentration, change_credits, change_schedule,
change_interests) are validated separately.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Optional

from .models import Course, Pathway, Program, SemesterPlan, Student
from .prerequisite_engine import PrerequisiteEngine
from .program_universe import program_courses


PREF_OP_TYPES = {
    "change_concentration",
    "change_credits",
    "change_schedule",
    "change_interests",
}
SCHEDULE_VALUES = {"morning", "afternoon", "evening", "no_preference"}


@dataclass
class ValidationResult:
    ok: bool
    error: Optional[str] = None


def _semester_key(term: str) -> int:
    """Return an integer key ordering "Spring 2027" < "Fall 2027", etc."""
    season, year = term.split()
    order = {"Spring": 0, "Summer": 1, "Fall": 2}
    return int(year) * 10 + order.get(season, 3)


def describe_op(op: dict[str, Any], courses: dict[str, Course]) -> str:
    """Human-readable description of an op for UI display."""
    t = op.get("type", "")
    if t == "change_concentration":
        return f"Switch concentration → {op.get('concentration')}"
    if t == "change_credits":
        return f"Change credit cap → {op.get('value')} credits per term"
    if t == "change_schedule":
        return f"Change schedule preference → {op.get('value')}"
    if t == "change_interests":
        v = op.get("value", [])
        if isinstance(v, list):
            v = ", ".join(v)
        return f"Update interests → {v}"
    course_id = op.get("course", "")
    course = courses.get(course_id)
    title = course.title if course else course_id
    if t == "move":
        return f"Move {course_id} ({title}) from {op.get('from_term')} → {op.get('to_term')}"
    if t == "remove":
        return f"Remove {course_id} ({title}) from {op.get('from_term')}"
    if t == "add":
        return f"Add {course_id} ({title}) to {op.get('to_term')}"
    return str(op)


def validate_operation(
    op: dict[str, Any],
    plan_state: dict[str, Any],
    program: Program,
    student: Student,
    engine: PrerequisiteEngine,
    catalog_programs: dict[str, Program],
) -> ValidationResult:
    """Validate a single operation against current plan state.

    plan_state is expected to look like {"semester_plans": [{"term": str, "courses": list[str]}, ...]}.
    """
    t = op.get("type")
    if not t:
        return ValidationResult(False, "Missing operation type")

    # --- Preference-op validation ---
    if t == "change_concentration":
        concentration = op.get("concentration")
        if not concentration:
            return ValidationResult(False, "Missing concentration name")
        if not program.concentrations:
            return ValidationResult(
                False, f"{program.program_id} has no concentrations to switch to"
            )
        match = next(
            (c for c in program.concentrations if c.name == concentration), None
        )
        if not match:
            available = ", ".join(c.name for c in program.concentrations)
            return ValidationResult(
                False,
                f'"{concentration}" is not a concentration in {program.program_id}. Available: {available}',
            )
        if concentration == student.preferences.concentration_choice:
            return ValidationResult(
                False, f'Already on the "{concentration}" concentration'
            )
        return ValidationResult(True)

    if t == "change_credits":
        v = op.get("value")
        if not isinstance(v, (int, float)) or v < 6 or v > 18:
            return ValidationResult(
                False, f"Credit cap must be 6-18 (got {v})"
            )
        return ValidationResult(True)

    if t == "change_schedule":
        v = op.get("value")
        if v not in SCHEDULE_VALUES:
            return ValidationResult(
                False,
                f'Schedule must be morning/afternoon/evening/no_preference (got "{v}")',
            )
        return ValidationResult(True)

    if t == "change_interests":
        v = op.get("value")
        if not isinstance(v, list):
            return ValidationResult(False, "Interests must be a list of strings")
        return ValidationResult(True)

    # --- Course-op validation ---
    course_id = op.get("course")
    if not course_id:
        return ValidationResult(False, "Missing course")
    if course_id not in engine.courses:
        return ValidationResult(False, f"Unknown course: {course_id}")

    # Program-scope guardrail — the single most important safety net
    universe = program_courses(program.program_id, catalog_programs, engine)
    if course_id not in universe:
        return ValidationResult(
            False,
            f"{course_id} is not in {program.program_id} — cross-program courses are not allowed",
        )

    # Cannot touch past or current terms
    current_key = _semester_key(student.current_semester)
    from_term = op.get("from_term")
    to_term = op.get("to_term")
    if from_term and _semester_key(from_term) <= current_key:
        return ValidationResult(False, f"Cannot modify past/current term ({from_term})")
    if to_term and _semester_key(to_term) <= current_key:
        return ValidationResult(
            False, f"Cannot schedule into past/current term ({to_term})"
        )

    semester_plans = plan_state.get("semester_plans", [])

    if t in ("move", "remove"):
        source_plan = next(
            (p for p in semester_plans if course_id in p["courses"]), None
        )
        if source_plan is None:
            return ValidationResult(
                False, f"{course_id} is not currently in the plan"
            )
        if t == "remove":
            return ValidationResult(True)
        if from_term and source_plan["term"] != from_term:
            return ValidationResult(
                False,
                f"{course_id} is in {source_plan['term']}, not {from_term}",
            )

    if t in ("move", "add"):
        if not to_term:
            return ValidationResult(False, "Missing destination term")
        season = to_term.split()[0].lower()
        course = engine.courses[course_id]
        offered = [s.value for s in course.semesters_offered]
        if offered and season not in offered:
            return ValidationResult(
                False,
                f"{course_id} is only offered in {'/'.join(offered)} — not {season}",
            )
        # Prereq check — what would be completed by the destination term?
        completed = set(student.completed_courses) | set(student.current_courses)
        target_key = _semester_key(to_term)
        for plan in semester_plans:
            if _semester_key(plan["term"]) < target_key:
                for cid in plan["courses"]:
                    if t == "move" and cid == course_id:
                        continue
                    completed.add(cid)
        status = engine.check_prereqs(course_id, completed)
        if not status.satisfied:
            missing = " AND ".join(
                "(" + " OR ".join(g) + ")" for g in status.missing
            )
            return ValidationResult(
                False,
                f"Prereqs for {course_id} not met by {to_term}: needs {missing}",
            )
        target_plan = next((p for p in semester_plans if p["term"] == to_term), None)
        if t == "add" and target_plan and course_id in target_plan["courses"]:
            return ValidationResult(
                False, f"{course_id} is already scheduled in {to_term}"
            )

    return ValidationResult(True)


def apply_operation_in_place(op: dict[str, Any], plan_state: dict[str, Any]) -> None:
    """Mutate plan_state to reflect the operation."""
    t = op.get("type")
    course_id = op.get("course")
    to_term = op.get("to_term")

    if t in ("move", "remove"):
        for plan in plan_state["semester_plans"]:
            plan["courses"] = [c for c in plan["courses"] if c != course_id]

    if t in ("move", "add"):
        target = next(
            (p for p in plan_state["semester_plans"] if p["term"] == to_term), None
        )
        if target is None:
            target = {
                "term": to_term,
                "courses": [],
                "total_credits": 0.0,
                "rationale": "User-added semester",
            }
            plan_state["semester_plans"].append(target)
            plan_state["semester_plans"].sort(key=lambda p: _semester_key(p["term"]))
        if course_id not in target["courses"]:
            target["courses"].append(course_id)


def apply_overrides(
    base_pathway: Pathway,
    overrides: list[dict[str, Any]],
    program: Program,
    student: Student,
    engine: PrerequisiteEngine,
    catalog_programs: dict[str, Program],
) -> dict[str, Any]:
    """Apply a list of override operations on top of the base pathway.

    Returns dict with:
      - semester_plans: mutated plans
      - warnings: original + any override rejection reasons
      - applied_ops
      - failed_ops
    """
    plan_state = {
        "semester_plans": [
            {"term": p.term, "courses": list(p.courses),
             "total_credits": p.total_credits, "rationale": p.rationale}
            for p in base_pathway.semester_plans
        ]
    }
    applied = []
    failed = []
    if not overrides:
        pass
    else:
        for op in overrides:
            check = validate_operation(op, plan_state, program, student, engine, catalog_programs)
            if not check.ok:
                failed.append({"op": op, "error": check.error})
                continue
            apply_operation_in_place(op, plan_state)
            applied.append(op)

    # Recalc credit totals and drop empty semesters
    for p in plan_state["semester_plans"]:
        p["total_credits"] = sum(
            engine.courses[c].credits if c in engine.courses else 3.0
            for c in p["courses"]
        )
    plan_state["semester_plans"] = [
        p for p in plan_state["semester_plans"] if p["courses"]
    ]

    warnings = list(base_pathway.warnings)
    for f in failed:
        warnings.append(
            f'Edit rejected — {describe_op(f["op"], engine.courses)}: {f["error"]}'
        )

    return {
        "semester_plans": plan_state["semester_plans"],
        "warnings": warnings,
        "applied_ops": applied,
        "failed_ops": failed,
    }


def diff_pathways(
    old_plans: list[dict[str, Any]],
    new_plans: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute a semantic diff between two pathways."""
    old_term_by_course = {}
    for p in old_plans:
        for c in p["courses"]:
            old_term_by_course[c] = p["term"]
    new_term_by_course = {}
    for p in new_plans:
        for c in p["courses"]:
            new_term_by_course[c] = p["term"]
    old_set = set(old_term_by_course)
    new_set = set(new_term_by_course)
    added = []
    removed = []
    moved = []
    unchanged = 0
    for c in new_set:
        if c not in old_set:
            added.append({"course": c, "term": new_term_by_course[c]})
        elif old_term_by_course[c] != new_term_by_course[c]:
            moved.append({
                "course": c,
                "from": old_term_by_course[c],
                "to": new_term_by_course[c],
            })
        else:
            unchanged += 1
    for c in old_set - new_set:
        removed.append({"course": c, "term": old_term_by_course[c]})
    return {
        "added": added,
        "removed": removed,
        "moved": moved,
        "unchanged": unchanged,
    }
