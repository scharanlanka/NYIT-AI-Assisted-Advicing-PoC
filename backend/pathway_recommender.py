"""
Personalized Learning Pathway Recommender.

Takes a student and their program, computes what they still need, orders
remaining courses respecting prerequisites, and distributes them across
semesters respecting the student's credit limits and each course's
semester offerings.

The LLM is NOT used here — this is deterministic constraint-satisfying
planning. The LLM (llm_service.py) is used only to explain WHY a plan
was generated, in natural language.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable

from models import (
    Course,
    Pathway,
    Program,
    RequirementBlock,
    SemesterPlan,
    Student,
    Semester,
)
from prerequisite_engine import PrerequisiteEngine


@dataclass
class RequirementStatus:
    block_name: str
    total_required_credits: float
    completed_credits: float
    completed_courses: list[str]
    remaining_options: list[str]  # course_ids the student could still choose from
    remaining_needed: int  # how many more courses (or credits) needed
    fully_satisfied: bool


class PathwayRecommender:
    """
    Generates a semester-by-semester course plan for a single student.

    Design
    ------
    1. Compute remaining requirements per block.
    2. For each remaining course, use the prereq engine to check when it
       becomes eligible given previously-scheduled courses.
    3. Greedy semester filling: for each upcoming semester, pick eligible
       courses that fit the student's credit budget and are offered that
       semester, prioritizing:
         (a) courses the student's concentration/interests point to
         (b) courses that unlock the most downstream requirements
         (c) core-required over concentration over elective
    """

    def __init__(
        self,
        program: Program,
        engine: PrerequisiteEngine,
    ):
        self.program = program
        self.engine = engine

    # ---------- Requirement analysis ----------

    def analyze_requirements(self, student: Student) -> list[RequirementStatus]:
        """For each requirement block in the program, figure out what's done
        and what's left."""
        completed = set(student.completed_courses) | set(student.current_courses)
        blocks = list(self.program.requirement_blocks)

        # Include selected concentration's blocks if the student picked one.
        if student.preferences.concentration_choice:
            for conc in self.program.concentrations:
                if conc.name == student.preferences.concentration_choice:
                    blocks.extend(conc.requirement_blocks)
                    break

        statuses: list[RequirementStatus] = []
        for block in blocks:
            block_completed = [c for c in block.course_ids if c in completed]
            block_completed_credits = sum(
                self.engine.courses[c].credits if c in self.engine.courses else 3.0
                for c in block_completed
            )
            target_credits = block.credits_required or 0.0
            if block.choose_n is not None:
                # "Pick N of these"
                remaining_needed = max(0, block.choose_n - len(block_completed))
                fully = remaining_needed == 0
                remaining = [c for c in block.course_ids if c not in completed]
            elif not block.course_ids and target_credits > 0:
                # Open-ended block: "N credits of electives, chosen with advisor".
                # Cannot auto-satisfy — advisor decides what counts.
                missing_cr = max(0.0, target_credits - block_completed_credits)
                remaining_needed = int(-(-missing_cr // 3))  # ceil-div by 3-cr default
                fully = block_completed_credits >= target_credits
                remaining = []
            else:
                # "All courses in this list required"
                remaining_needed = max(0, len(block.course_ids) - len(block_completed))
                fully = (
                    len(block.course_ids) > 0
                    and all(c in completed for c in block.course_ids)
                )
                remaining = [c for c in block.course_ids if c not in completed]

            statuses.append(
                RequirementStatus(
                    block_name=block.name,
                    total_required_credits=target_credits,
                    completed_credits=block_completed_credits,
                    completed_courses=block_completed,
                    remaining_options=remaining,
                    remaining_needed=remaining_needed,
                    fully_satisfied=fully,
                )
            )
        return statuses

    def remaining_course_pool(
        self, student: Student, statuses: list[RequirementStatus]
    ) -> list[str]:
        """Flat list of course_ids the student still needs (or could still
        pick from). De-duplicated, non-completed."""
        completed = set(student.completed_courses) | set(student.current_courses)
        pool: list[str] = []
        seen: set[str] = set()
        for s in statuses:
            if s.fully_satisfied:
                continue
            for cid in s.remaining_options:
                if cid in seen or cid in completed:
                    continue
                if not cid or "XXX" in cid or " 3XX" in cid:
                    continue  # skip placeholder "any 300-level" slots
                seen.add(cid)
                pool.append(cid)
        return pool

    # ---------- Semester planning ----------

    @staticmethod
    def _next_semester(term: str) -> str:
        season, year = term.split()
        y = int(year)
        if season == "Fall":
            return f"Spring {y + 1}"
        if season == "Spring":
            return f"Fall {y}"
        return f"Fall {y + 1}"  # skip summer by default

    @staticmethod
    def _semester_key(term: str) -> tuple[int, int]:
        season, year = term.split()
        order = {"Spring": 0, "Summer": 1, "Fall": 2}
        return (int(year), order.get(season, 3))

    def _prioritize(self, course_id: str, student: Student) -> float:
        """Higher score = pick sooner. Combines category, interests, and
        downstream-unlock potential."""
        course = self.engine.courses.get(course_id)
        if course is None:
            return 0.0
        score = 0.0
        if course.category.value == "core_required":
            score += 3.0
        elif course.category.value == "concentration":
            score += 2.0
        elif course.category.value == "capstone":
            score += 0.5
        else:
            score += 1.0
        interests = [i.lower() for i in student.preferences.interests]
        for tag in course.tags:
            if any(intr in tag or tag in intr for intr in interests):
                score += 1.0
        # Prefer lower-level courses first
        try:
            level_penalty = int(course.level[0]) * 0.1
            score -= level_penalty
        except (ValueError, IndexError):
            pass
        # Downstream unlock bonus
        score += 0.1 * len(self.engine.dependents(course_id))
        return score

    def generate_pathway(self, student: Student) -> Pathway:
        statuses = self.analyze_requirements(student)
        pool = self.remaining_course_pool(student, statuses)

        # Running set of "already done or scheduled" course_ids
        scheduled: set[str] = set(student.completed_courses) | set(student.current_courses)
        semester_plans: list[SemesterPlan] = []
        warnings: list[str] = []

        current_term = student.current_semester
        # Skip past the "current" semester since the student is IN it — start
        # from the next planned term.
        current_term = self._next_semester(current_term)

        target_key = self._semester_key(student.target_graduation)
        max_semesters = 12  # safety valve
        unplaceable_streak = 0

        while pool and len(semester_plans) < max_semesters:
            season = current_term.split()[0].lower()
            try:
                season_enum = Semester(season)
            except ValueError:
                season_enum = Semester.FALL

            # Which pool courses are eligible AND offered this semester?
            candidates: list[tuple[float, str]] = []
            for cid in pool:
                status = self.engine.check_prereqs(cid, scheduled)
                if not status.satisfied:
                    continue
                course = self.engine.courses.get(cid)
                if course and season_enum not in course.semesters_offered:
                    continue
                candidates.append((self._prioritize(cid, student), cid))

            candidates.sort(key=lambda p: (-p[0], p[1]))

            picked: list[str] = []
            picked_credits = 0.0
            max_cr = student.preferences.max_credits_per_semester

            for _, cid in candidates:
                course = self.engine.courses.get(cid)
                credits = course.credits if course else 3.0
                if picked_credits + credits > max_cr:
                    continue
                picked.append(cid)
                picked_credits += credits

            if not picked:
                # Nothing was eligible/offered this term — advance calendar.
                unplaceable_streak += 1
                if unplaceable_streak >= 3:
                    warnings.append(
                        f"Could not place any remaining courses over 3 consecutive terms starting {current_term}. "
                        f"Remaining pool: {pool}"
                    )
                    break
                current_term = self._next_semester(current_term)
                continue

            unplaceable_streak = 0
            plan = SemesterPlan(
                term=current_term,
                courses=picked,
                total_credits=picked_credits,
                rationale=self._brief_rationale(picked, student),
            )
            semester_plans.append(plan)
            for cid in picked:
                scheduled.add(cid)
                if cid in pool:
                    pool.remove(cid)

            if self._semester_key(current_term) >= target_key and not pool:
                break
            current_term = self._next_semester(current_term)

        if pool:
            warnings.append(
                f"Could not schedule all remaining requirements before {student.target_graduation}. "
                f"Still needed: {pool[:5]}{'...' if len(pool) > 5 else ''}"
            )

        summary_lines = [
            f"Program: {self.program.name} ({self.program.catalog_year})",
            f"Student: {student.name} ({student.student_id})",
            f"Target graduation: {student.target_graduation}",
            f"Plans generated for {len(semester_plans)} upcoming semester(s).",
        ]
        return Pathway(
            student_id=student.student_id,
            generated_at=datetime.utcnow().isoformat() + "Z",
            semester_plans=semester_plans,
            summary="\n".join(summary_lines),
            warnings=warnings,
        )

    def _brief_rationale(self, picked: list[str], student: Student) -> str:
        interests = ", ".join(student.preferences.interests) or "core progression"
        return f"Advances {interests}; respects prereqs and {student.preferences.max_credits_per_semester}-credit cap."
