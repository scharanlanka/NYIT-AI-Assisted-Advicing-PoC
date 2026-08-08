"""
Degree completion analysis — computes whether the current pathway (past +
current + planned) would actually fulfill the degree requirements, and
surfaces any gaps.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from models import Program, Student
from prerequisite_engine import PrerequisiteEngine


@dataclass
class BlockCompletion:
    block_name: str
    target: float
    covered_credits: float
    covered_courses: list[str]
    will_be_satisfied: bool
    gap_credits: float
    is_open: bool
    notes: str
    choose_n: Optional[int]
    course_ids: list[str]


@dataclass
class DegreeCompletion:
    total_target: float
    total_scheduled_credits: float
    percent_complete: int
    block_analysis: list[BlockCompletion]
    incomplete_blocks: list[BlockCompletion]
    total_gap: float
    is_fully_on_track: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_target": self.total_target,
            "total_scheduled_credits": self.total_scheduled_credits,
            "percent_complete": self.percent_complete,
            "block_analysis": [b.__dict__ for b in self.block_analysis],
            "incomplete_blocks": [b.__dict__ for b in self.incomplete_blocks],
            "total_gap": self.total_gap,
            "is_fully_on_track": self.is_fully_on_track,
        }


def analyze_completion_across_plan(
    student: Student,
    program: Program,
    planned_courses: list[str],
    engine: PrerequisiteEngine,
) -> list[BlockCompletion]:
    """Consider past + current + planned as the "scheduled" set and check which
    requirement blocks would be fulfilled."""
    scheduled = set(student.completed_courses) | set(student.current_courses) | set(planned_courses)
    blocks = list(program.requirement_blocks)
    if student.preferences.concentration_choice:
        for conc in program.concentrations:
            if conc.name == student.preferences.concentration_choice:
                blocks.extend(conc.requirement_blocks)
                break

    results: list[BlockCompletion] = []
    for block in blocks:
        covered = [c for c in block.course_ids if c in scheduled]
        covered_credits = sum(
            engine.courses[c].credits if c in engine.courses else 3.0 for c in covered
        )
        target = float(block.credits_required or 0)
        is_open = len(block.course_ids) == 0 and target > 0

        if block.choose_n is not None:
            will_be_satisfied = len(covered) >= block.choose_n
            gap_credits = 0.0 if will_be_satisfied else (block.choose_n - len(covered)) * 3.0
        elif is_open:
            will_be_satisfied = covered_credits >= target
            gap_credits = max(0.0, target - covered_credits)
        else:
            will_be_satisfied = bool(block.course_ids) and all(
                c in scheduled for c in block.course_ids
            )
            gap_credits = max(0.0, target - covered_credits)

        results.append(
            BlockCompletion(
                block_name=block.name,
                target=target,
                covered_credits=covered_credits,
                covered_courses=covered,
                will_be_satisfied=will_be_satisfied,
                gap_credits=gap_credits,
                is_open=is_open,
                notes=block.notes or "",
                choose_n=block.choose_n,
                course_ids=list(block.course_ids),
            )
        )
    return results


def compute_degree_completion(
    student: Student,
    program: Program,
    planned_courses: list[str],
    engine: PrerequisiteEngine,
) -> DegreeCompletion:
    block_analysis = analyze_completion_across_plan(
        student, program, planned_courses, engine
    )
    scheduled = set(student.completed_courses) | set(student.current_courses) | set(planned_courses)
    total_scheduled = sum(
        engine.courses[c].credits if c in engine.courses else 0 for c in scheduled
    )
    incomplete = [b for b in block_analysis if not b.will_be_satisfied]
    total_gap = sum(b.gap_credits for b in incomplete)
    percent_complete = (
        min(100, round(total_scheduled / program.total_credits * 100))
        if program.total_credits > 0
        else 0
    )
    return DegreeCompletion(
        total_target=program.total_credits,
        total_scheduled_credits=total_scheduled,
        percent_complete=percent_complete,
        block_analysis=block_analysis,
        incomplete_blocks=incomplete,
        total_gap=total_gap,
        is_fully_on_track=len(incomplete) == 0,
    )
