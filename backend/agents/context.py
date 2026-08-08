"""
Curriculum Context Provider — deterministic (not LLM) context builder.

Assembles rich structured context so every specialist agent has the same
program-aware facts. Prevents context-shortage failures that were
misclassified as reasoning failures.
"""
from __future__ import annotations

from typing import Any

from ..models import Pathway, Program, Student
from ..prerequisite_engine import PrerequisiteEngine
from ..program_universe import program_courses


def build_curriculum_context(
    student: Student,
    program: Program,
    pathway: Pathway,
    programs: dict[str, Program],
    engine: PrerequisiteEngine,
) -> dict[str, Any]:
    universe = sorted(program_courses(program.program_id, programs, engine))
    required_courses: set[str] = set()
    for block in program.requirement_blocks:
        required_courses.update(block.course_ids)

    concentration_details = []
    for c in program.concentrations:
        conc_courses = []
        for block in c.requirement_blocks:
            for cid in block.course_ids:
                if cid:
                    conc_courses.append(cid)
        concentration_details.append(
            {
                "name": c.name,
                "description": c.description or "",
                "courses": conc_courses,
            }
        )

    if not pathway.semester_plans:
        current_plan_text = "  (no future plan yet)"
    else:
        lines = []
        for p in pathway.semester_plans:
            lines.append(
                f"  {p.term} ({p.total_credits:.0f} cr): {', '.join(p.courses)}"
            )
        current_plan_text = "\n".join(lines)

    return {
        "student": {
            "name": student.name,
            "id": student.student_id,
            "currentTerm": student.current_semester,
            "targetGrad": student.target_graduation,
            "completed": student.completed_courses,
            "current": student.current_courses,
            "interests": student.preferences.interests,
            "concentration": student.preferences.concentration_choice,
            "maxCredits": student.preferences.max_credits_per_semester,
            "schedule": student.preferences.preferred_schedule.value,
        },
        "program": {
            "id": program.program_id,
            "name": program.name,
            "level": program.level.value,
            "totalCredits": program.total_credits,
            "concentrations": concentration_details,
        },
        "universe": universe,
        "requiredCourses": sorted(required_courses),
        "currentPlan": current_plan_text,
    }
