"""
Compute the "course universe" for a program: every course in its requirement
blocks + concentrations + all transitive prereqs, plus courses in the primary
department at the same academic level (grad/undergrad).

This is what the Prereq Explorer dropdown and the AI editor guardrails use to
prevent cross-program mixing.
"""
from __future__ import annotations

from functools import lru_cache

from .models import Course, Program
from .prerequisite_engine import PrerequisiteEngine


_CACHE: dict[str, set[str]] = {}


def program_courses(
    program_id: str,
    programs: dict[str, Program],
    engine: PrerequisiteEngine,
) -> set[str]:
    """Return the set of course IDs that make up this program's course universe."""
    if program_id in _CACHE:
        return _CACHE[program_id]
    program = programs.get(program_id)
    if program is None:
        return set()
    universe: set[str] = set()

    def add_with_prereqs(cid: str) -> None:
        if not cid or "XXX" in cid or " 3XX" in cid:
            return
        if cid in universe:
            return
        chain = engine.prereq_chain(cid)
        for c in chain:
            if "XXX" not in c and " 3XX" not in c:
                universe.add(c)

    for block in program.requirement_blocks:
        for cid in block.course_ids:
            add_with_prereqs(cid)
    for conc in program.concentrations:
        for block in conc.requirement_blocks:
            for cid in block.course_ids:
                add_with_prereqs(cid)

    # Include every course in the program's primary department at the right
    # academic level (grad = 600+, undergrad = 100-500). Pulls in electives
    # that aren't explicitly named in a requirement block.
    is_grad = program.level.value == "graduate"
    for cid, course in engine.courses.items():
        if course.department != program.department:
            continue
        try:
            level_int = int(course.level[0])
        except (ValueError, IndexError):
            level_int = 0
        grad_level = level_int >= 6
        if is_grad == grad_level:
            add_with_prereqs(cid)

    _CACHE[program_id] = universe
    return universe


def program_elective_pool(
    program_id: str,
    student_concentration: str | None,
    programs: dict[str, Program],
    engine: PrerequisiteEngine,
) -> list[str]:
    """Courses in the program universe that aren't nailed to any required
    or chosen-concentration block — plausible candidates to fill open-ended
    "N credits of electives" requirements."""
    program = programs.get(program_id)
    if program is None:
        return []
    universe = program_courses(program_id, programs, engine)
    required: set[str] = set()
    for block in program.requirement_blocks:
        required.update(block.course_ids)
    if student_concentration:
        chosen = next(
            (c for c in program.concentrations if c.name == student_concentration),
            None,
        )
        if chosen:
            for block in chosen.requirement_blocks:
                required.update(block.course_ids)
    return sorted(
        cid for cid in universe if cid not in required and cid in engine.courses
    )
