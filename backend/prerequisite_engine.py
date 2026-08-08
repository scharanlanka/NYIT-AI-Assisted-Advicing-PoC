"""
Deterministic prerequisite resolution over NYIT's disjunctive prereq structure.

The LLM is NOT involved here — this is a graph problem and should be exact.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Iterable

from .models import Course


@dataclass
class PrereqStatus:
    course_id: str
    satisfied: bool
    satisfied_groups: list[bool]              # per-group AND result
    missing: list[list[str]]                  # groups the student still needs one from
    already_completed: list[str]              # prereqs the student has already taken


class PrerequisiteEngine:
    """
    Builds an index of courses and answers questions about the prereq graph.

    Prereq semantics
    ----------------
    A course C has prerequisite_groups = [G1, G2, ..., Gn].
    Each Gi is a list of alternatives.
    C's prereqs are satisfied iff for every Gi at least one course in Gi has been
    completed. This is AND across groups, OR within a group.
    """

    def __init__(self, courses: Iterable[Course]):
        self.courses: dict[str, Course] = {c.course_id: c for c in courses}
        # Reverse index: for each prereq course, which courses depend on it.
        self._dependents: dict[str, set[str]] = defaultdict(set)
        for c in self.courses.values():
            for group in c.prerequisite_groups:
                for prereq_id in group:
                    self._dependents[prereq_id].add(c.course_id)

    # ---------- Prereq checking ----------

    def check_prereqs(self, course_id: str, completed: set[str]) -> PrereqStatus:
        """Return a status object describing whether the student has satisfied
        the prereqs of `course_id`, and if not, what's missing."""
        course = self.courses.get(course_id)
        if course is None:
            raise KeyError(f"Unknown course: {course_id}")

        if not course.prerequisite_groups:
            return PrereqStatus(course_id, True, [], [], [])

        satisfied_groups: list[bool] = []
        missing: list[list[str]] = []
        already: list[str] = []

        for group in course.prerequisite_groups:
            hits = [p for p in group if p in completed]
            if hits:
                satisfied_groups.append(True)
                already.extend(hits)
            else:
                satisfied_groups.append(False)
                missing.append(group)

        return PrereqStatus(
            course_id=course_id,
            satisfied=all(satisfied_groups),
            satisfied_groups=satisfied_groups,
            missing=missing,
            already_completed=already,
        )

    # ---------- Chain resolution ----------

    def prereq_chain(self, course_id: str) -> dict[str, list[list[str]]]:
        """Return the full transitive prereq chain reachable from `course_id`.

        Result maps each reachable course_id -> its prerequisite_groups
        (so callers can render the graph). Unknown course codes (e.g. courses
        that appear as OR-alternatives but aren't in our catalog) are included
        with empty prereqs to preserve the graph structure."""
        chain: dict[str, list[list[str]]] = {}
        queue: deque[str] = deque([course_id])
        while queue:
            cid = queue.popleft()
            if cid in chain:
                continue
            course = self.courses.get(cid)
            if course is None:
                chain[cid] = []
                continue
            chain[cid] = [list(g) for g in course.prerequisite_groups]
            for group in course.prerequisite_groups:
                for prereq_id in group:
                    if prereq_id not in chain:
                        queue.append(prereq_id)
        return chain

    def eligible_courses(self, completed: set[str]) -> list[str]:
        """All courses in the catalog whose prereqs the student has satisfied
        and which they have not yet taken."""
        result = []
        for cid, course in self.courses.items():
            if cid in completed:
                continue
            status = self.check_prereqs(cid, completed)
            if status.satisfied:
                result.append(cid)
        return sorted(result)

    def unlocks(self, course_id: str, completed: set[str]) -> list[str]:
        """Which currently-blocked courses would become eligible if the student
        added `course_id` to their completed set."""
        hypothetical = completed | {course_id}
        before = set(self.eligible_courses(completed))
        after = set(self.eligible_courses(hypothetical))
        return sorted(after - before - {course_id})

    def dependents(self, course_id: str) -> list[str]:
        """Direct downstream courses that list `course_id` as a possible prereq."""
        return sorted(self._dependents.get(course_id, set()))

    # ---------- Topological ordering ----------

    def topological_layers(self, course_ids: Iterable[str]) -> list[list[str]]:
        """
        Group the given courses into "levels" such that a course only appears
        after all of its prereqs (that are in the set) have appeared.

        Layer 0 = courses whose prereqs are entirely outside the set (or none).
        This is what the semester-plan builder uses to place courses in order.
        """
        target = set(course_ids)
        layers: list[list[str]] = []
        placed: set[str] = set()

        while len(placed) < len(target):
            layer = []
            for cid in target - placed:
                course = self.courses.get(cid)
                if course is None:
                    layer.append(cid)
                    continue
                # A course is placeable if for every prereq group at least one
                # option is either outside the target set or already placed.
                placeable = True
                for group in course.prerequisite_groups:
                    if not any(p in placed or p not in target for p in group):
                        placeable = False
                        break
                if placeable:
                    layer.append(cid)
            if not layer:
                # Cycle or unsatisfiable — bail with the remainder as one layer
                # so the caller can surface a warning.
                layers.append(sorted(target - placed))
                break
            layer.sort()
            layers.append(layer)
            placed.update(layer)

        return layers
