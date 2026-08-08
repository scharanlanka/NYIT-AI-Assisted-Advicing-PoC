"""
Data models for the NYIT AI-Assisted Advising POC.

Design notes
------------
NYIT catalog prerequisites are commonly *disjunctive* — e.g. CSCI 260's prereq is
"MATH 161 or MATH 170, and CSCI 185". A naive `prerequisites: list[str]` cannot
express that. We model prereqs as a list of *groups*, where each group is a set
of alternatives (OR within the group, AND across groups):

    CSCI 260 prereqs -> [
        ["MATH 161", "MATH 170"],   # any one of these
        ["CSCI 185"],                # AND this
    ]

This mirrors how the semester-map PDFs write prereqs and lets the graph engine
resolve "student has satisfied prereqs iff for every group they've completed at
least one course in that group."
"""
from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ---------- Course catalog ----------

class Semester(str, Enum):
    FALL = "fall"
    SPRING = "spring"
    SUMMER = "summer"


class CourseCategory(str, Enum):
    CORE_REQUIRED = "core_required"          # required for the major
    CONCENTRATION = "concentration"          # concentration-specific course
    MATH_REQUIRED = "math_required"
    SCIENCE_REQUIRED = "science_required"
    GEN_ED = "gen_ed"                        # general education
    ELECTIVE = "elective"
    CAPSTONE = "capstone"


class Course(BaseModel):
    """A single course. Fields chosen to match NYIT's public catalog format."""
    course_id: str = Field(..., description="e.g. 'CSCI 260'")
    title: str
    credits: float
    description: str = ""
    # Prereq groups: list of alternative-lists. AND across groups, OR within.
    prerequisite_groups: list[list[str]] = Field(default_factory=list)
    # Corequisites — must be taken concurrently OR earlier.
    corequisites: list[str] = Field(default_factory=list)
    department: str = Field(..., description="e.g. 'Computer Science'")
    level: str = Field(..., description="'100'/'200'/'300'/'400'/'500'/'600'/'700'")
    semesters_offered: list[Semester] = Field(default_factory=lambda: [Semester.FALL, Semester.SPRING])
    category: CourseCategory = CourseCategory.CORE_REQUIRED
    tags: list[str] = Field(default_factory=list)
    min_grade: str = Field(default="C-", description="Minimum passing grade to satisfy as prereq")

    def has_prereqs(self) -> bool:
        return bool(self.prerequisite_groups)


# ---------- Program / degree structure ----------

class ProgramLevel(str, Enum):
    UNDERGRAD = "undergrad"
    GRADUATE = "graduate"


class RequirementBlock(BaseModel):
    """
    A named block of the degree (e.g. 'Core Computer Science', 'AI Concentration
    — choose 4'). Lets the recommender reason about remaining requirements at a
    block level, not just individual courses.
    """
    name: str
    course_ids: list[str] = Field(default_factory=list)
    # How many courses from `course_ids` the student must complete.
    # If None, all courses are required.
    choose_n: Optional[int] = None
    credits_required: Optional[float] = None
    notes: str = ""


class Concentration(BaseModel):
    """Optional concentration within a program (e.g. 'Artificial Intelligence')."""
    name: str
    requirement_blocks: list[RequirementBlock] = Field(default_factory=list)
    description: str = ""


class Program(BaseModel):
    """A degree program (e.g. Computer Science BS)."""
    program_id: str = Field(..., description="e.g. 'CS_BS', 'AI_MS'")
    name: str
    level: ProgramLevel
    college: str = "College of Engineering and Computing Sciences"
    department: str
    catalog_year: str = Field(..., description="e.g. '2026-2027'")
    total_credits: float
    requirement_blocks: list[RequirementBlock] = Field(default_factory=list)
    concentrations: list[Concentration] = Field(default_factory=list)
    catalog_url: str = ""


# ---------- Student profile (synthetic) ----------

class SchedulePreference(str, Enum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    NO_PREFERENCE = "no_preference"


class StudentPreferences(BaseModel):
    interests: list[str] = Field(default_factory=list)
    max_credits_per_semester: int = 15
    min_credits_per_semester: int = 12
    preferred_schedule: SchedulePreference = SchedulePreference.NO_PREFERENCE
    concentration_choice: Optional[str] = None
    notes: str = ""


class Student(BaseModel):
    """
    Fully synthetic student profile. IMPORTANT: no real student data.
    """
    student_id: str
    name: str
    program_id: str = Field(..., description="Foreign key to Program.program_id")
    catalog_year: str
    current_semester: str = Field(..., description="e.g. 'Fall 2026'")
    target_graduation: str = Field(..., description="e.g. 'Spring 2028'")
    completed_courses: list[str] = Field(default_factory=list)
    current_courses: list[str] = Field(default_factory=list)
    gpa: Optional[float] = None
    preferences: StudentPreferences = Field(default_factory=StudentPreferences)


# ---------- Recommender output ----------

class SemesterPlan(BaseModel):
    term: str = Field(..., description="e.g. 'Fall 2026'")
    courses: list[str] = Field(default_factory=list)
    total_credits: float = 0.0
    rationale: str = ""


class Pathway(BaseModel):
    student_id: str
    generated_at: str
    semester_plans: list[SemesterPlan]
    summary: str = ""
    warnings: list[str] = Field(default_factory=list)
