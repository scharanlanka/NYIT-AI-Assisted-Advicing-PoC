"""
NYIT AI-Assisted Advising POC — FastAPI backend.

Run:
    uvicorn backend.main:app --reload --port 8001

Endpoints:
    Data:
      GET  /health
      GET  /programs
      GET  /programs/{id}
      GET  /students
      GET  /students/{id}
      GET  /courses
      GET  /courses/{id}
      GET  /courses/{id}/prereq-chain
      GET  /courses/{id}/dependents

    Program-scoped:
      GET  /programs/{id}/universe          — course IDs relevant to this program

    Pathway (stateless — client owns overrides):
      POST /pathway/generate                — base plan for a student (accepts pref overrides)
      POST /pathway/with-overrides          — base + override operations, returns applied plan + diff
      POST /pathway/completion              — degree completion analysis
      POST /pathway/history                 — reconstruct historical semesters
      POST /pathway/validate-operation      — check if an op is legal without applying

    Multi-agent:
      POST /agents/orchestrate              — router → specialist chain, returns proposed ops
      POST /agents/explain                  — LLM-generated rationale for a plan
      POST /agents/advisor-summary          — LLM-generated advisor memo
      POST /agents/chat                     — free-form chat grounded in the plan
"""
from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .agents.orchestrator import orchestrate
from .completion import compute_degree_completion
from .history import reconstruct_history
from .llm_service import LLMService
from .models import Course, Pathway, Program, Student, StudentPreferences
from .operations import (
    apply_overrides,
    describe_op,
    diff_pathways,
    validate_operation,
)
from .pathway_recommender import PathwayRecommender
from .prerequisite_engine import PrerequisiteEngine
from .program_universe import program_courses, program_elective_pool

DATA_DIR = Path(__file__).parent / "data"

app = FastAPI(
    title="NYIT AI-Assisted Advising POC",
    description="Multi-agent advising system with strict guardrails. "
                "Uses NYIT's public 2026-2027 catalog. Student data is synthetic.",
    version="0.4.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Data loading (cached) ----------

@lru_cache(maxsize=1)
def _load_data() -> tuple[list[Course], dict[str, Program], list[Student]]:
    catalog = json.loads((DATA_DIR / "course_catalog.json").read_text())
    programs_raw = json.loads((DATA_DIR / "programs.json").read_text())
    students_raw = json.loads((DATA_DIR / "sample_students.json").read_text())
    courses = [
        Course(**{k: v for k, v in c.items() if k != "used_by_programs"})
        for c in catalog["courses"]
    ]
    programs = {p["program_id"]: Program(**p) for p in programs_raw["programs"]}
    students = [Student(**s) for s in students_raw["students"]]
    return courses, programs, students


@lru_cache(maxsize=1)
def _engine() -> PrerequisiteEngine:
    courses, _, _ = _load_data()
    return PrerequisiteEngine(courses)


@lru_cache(maxsize=1)
def _llm() -> LLMService:
    return LLMService()


def _student_by_id(student_id: str) -> Student:
    _, _, students = _load_data()
    for s in students:
        if s.student_id == student_id:
            return s
    raise HTTPException(status_code=404, detail=f"Student {student_id} not found")


def _program_by_id(program_id: str) -> Program:
    _, programs, _ = _load_data()
    if program_id not in programs:
        raise HTTPException(status_code=404, detail=f"Program {program_id} not found")
    return programs[program_id]


def _apply_prefs_override(student: Student, override: Optional[dict[str, Any]]) -> Student:
    if not override:
        return student
    # Build a new Student with overridden preferences
    base_prefs = student.preferences.model_dump()
    for k, v in override.items():
        if k in base_prefs and v is not None:
            base_prefs[k] = v
    new_prefs = StudentPreferences(**base_prefs)
    return Student(**{**student.model_dump(), "preferences": new_prefs.model_dump()})


# ---------- Basic endpoints ----------

@app.get("/health")
def health():
    courses, programs, students = _load_data()
    return {
        "status": "ok",
        "programs": len(programs),
        "courses": len(courses),
        "students": len(students),
        "llm_provider": _llm().provider,
    }


@app.get("/programs")
def list_programs():
    _, programs, _ = _load_data()
    return {
        "programs": [
            {
                "program_id": p.program_id,
                "name": p.name,
                "level": p.level.value,
                "department": p.department,
                "total_credits": p.total_credits,
                "concentrations": [c.name for c in p.concentrations],
                "catalog_url": p.catalog_url,
            }
            for p in programs.values()
        ]
    }


@app.get("/programs/{program_id}")
def get_program(program_id: str):
    return _program_by_id(program_id).model_dump()


@app.get("/programs/{program_id}/universe")
def get_program_universe(program_id: str):
    _, programs, _ = _load_data()
    engine = _engine()
    universe = program_courses(program_id, programs, engine)
    return {
        "program_id": program_id,
        "count": len(universe),
        "courses": sorted(universe),
    }


@app.get("/students")
def list_students():
    _, _, students = _load_data()
    return {
        "students": [
            {
                "student_id": s.student_id,
                "name": s.name,
                "program_id": s.program_id,
                "current_semester": s.current_semester,
                "target_graduation": s.target_graduation,
                "gpa": s.gpa,
            }
            for s in students
        ]
    }


@app.get("/students/{student_id}")
def get_student(student_id: str):
    return _student_by_id(student_id).model_dump()


@app.get("/courses")
def list_courses(department: Optional[str] = None, level: Optional[str] = None):
    courses, _, _ = _load_data()
    filtered = courses
    if department:
        filtered = [c for c in filtered if c.department == department]
    if level:
        filtered = [c for c in filtered if c.level == level]
    return {
        "courses": [
            {
                "course_id": c.course_id,
                "title": c.title,
                "credits": c.credits,
                "department": c.department,
                "level": c.level,
                "semesters_offered": [s.value for s in c.semesters_offered],
            }
            for c in filtered
        ]
    }


@app.get("/courses/{course_id}")
def get_course(course_id: str):
    engine = _engine()
    if course_id not in engine.courses:
        raise HTTPException(status_code=404, detail=f"Course {course_id} not found")
    return engine.courses[course_id].model_dump()


@app.get("/courses/{course_id}/prereq-chain")
def get_prereq_chain(course_id: str):
    engine = _engine()
    if course_id not in engine.courses:
        raise HTTPException(status_code=404, detail=f"Course {course_id} not found")
    chain = engine.prereq_chain(course_id)
    edges = []
    for target, groups in chain.items():
        for group in groups:
            for source in group:
                edges.append({"source": source, "target": target})
    return {
        "target": course_id,
        "nodes": list(chain.keys()),
        "edges": edges,
        "prereq_groups_by_course": chain,
    }


@app.get("/courses/{course_id}/dependents")
def get_dependents(course_id: str):
    return {
        "course_id": course_id,
        "direct_dependents": _engine().dependents(course_id),
    }


# ---------- Pathway endpoints ----------

class PathwayRequest(BaseModel):
    student_id: str
    prefs_override: Optional[dict[str, Any]] = None


class PathwayWithOverridesRequest(BaseModel):
    student_id: str
    prefs_override: Optional[dict[str, Any]] = None
    pathway_overrides: list[dict[str, Any]] = []
    previous_plans: Optional[list[dict[str, Any]]] = None  # for computing diff


@app.post("/pathway/generate")
def generate_pathway(req: PathwayRequest):
    _, programs, _ = _load_data()
    base_student = _student_by_id(req.student_id)
    student = _apply_prefs_override(base_student, req.prefs_override)
    program = _program_by_id(student.program_id)
    recommender = PathwayRecommender(program, _engine())
    pathway = recommender.generate_pathway(student)
    return pathway.model_dump()


@app.post("/pathway/with-overrides")
def pathway_with_overrides(req: PathwayWithOverridesRequest):
    _, programs, _ = _load_data()
    engine = _engine()
    base_student = _student_by_id(req.student_id)
    student = _apply_prefs_override(base_student, req.prefs_override)
    program = _program_by_id(student.program_id)
    recommender = PathwayRecommender(program, engine)
    base_pathway = recommender.generate_pathway(student)

    result = apply_overrides(
        base_pathway, req.pathway_overrides, program, student, engine, programs
    )

    # Requirements analysis (pre-overrides for the block list)
    statuses = recommender.analyze_requirements(student)
    status_dicts = [
        {
            "block_name": s.block_name,
            "total_required_credits": s.total_required_credits,
            "completed_credits": s.completed_credits,
            "completed_courses": s.completed_courses,
            "remaining_options": s.remaining_options,
            "remaining_needed": s.remaining_needed,
            "fully_satisfied": s.fully_satisfied,
        }
        for s in statuses
    ]

    # Compute diff if previous plans were sent
    diff = None
    if req.previous_plans is not None:
        diff = diff_pathways(req.previous_plans, result["semester_plans"])

    # Completion analysis
    planned_courses = [
        c for p in result["semester_plans"] for c in p["courses"]
    ]
    completion = compute_degree_completion(student, program, planned_courses, engine)

    # History
    history = reconstruct_history(student, engine)

    # Current term as its own "plan"
    current_term_plan = None
    if student.current_courses:
        current_term_plan = {
            "term": student.current_semester,
            "courses": student.current_courses,
            "total_credits": sum(
                engine.courses[c].credits if c in engine.courses else 3.0
                for c in student.current_courses
            ),
            "rationale": "",
            "current": True,
        }

    return {
        "student": student.model_dump(),
        "program": program.model_dump(),
        "pathway": {
            "student_id": student.student_id,
            "semester_plans": result["semester_plans"],
            "warnings": result["warnings"],
            "generated_at": datetime.utcnow().isoformat() + "Z",
        },
        "history": history,
        "current_term_plan": current_term_plan,
        "requirement_blocks": status_dicts,
        "completion": completion.to_dict(),
        "applied_ops": result["applied_ops"],
        "failed_ops": result["failed_ops"],
        "diff": diff,
    }


class OperationValidateRequest(BaseModel):
    student_id: str
    prefs_override: Optional[dict[str, Any]] = None
    pathway_overrides: list[dict[str, Any]] = []
    operation: dict[str, Any]


@app.post("/pathway/validate-operation")
def validate_op_endpoint(req: OperationValidateRequest):
    _, programs, _ = _load_data()
    engine = _engine()
    base_student = _student_by_id(req.student_id)
    student = _apply_prefs_override(base_student, req.prefs_override)
    program = _program_by_id(student.program_id)
    recommender = PathwayRecommender(program, engine)
    base_pathway = recommender.generate_pathway(student)
    result = apply_overrides(
        base_pathway, req.pathway_overrides, program, student, engine, programs
    )
    plan_state = {"semester_plans": result["semester_plans"]}
    check = validate_operation(req.operation, plan_state, program, student, engine, programs)
    return {
        "ok": check.ok,
        "error": check.error,
        "description": describe_op(req.operation, engine.courses),
    }


# ---------- Multi-agent endpoints ----------

class OrchestrateRequest(BaseModel):
    student_id: str
    query: str
    prefs_override: Optional[dict[str, Any]] = None
    pathway_overrides: list[dict[str, Any]] = []


@app.post("/agents/orchestrate")
async def orchestrate_endpoint(req: OrchestrateRequest):
    _, programs, _ = _load_data()
    engine = _engine()
    base_student = _student_by_id(req.student_id)
    student = _apply_prefs_override(base_student, req.prefs_override)
    program = _program_by_id(student.program_id)
    recommender = PathwayRecommender(program, engine)
    base_pathway = recommender.generate_pathway(student)
    # Apply existing overrides so the agent sees the current pathway state
    override_result = apply_overrides(
        base_pathway, req.pathway_overrides, program, student, engine, programs
    )
    from .models import SemesterPlan
    current_pathway = Pathway(
        student_id=student.student_id,
        generated_at=datetime.utcnow().isoformat() + "Z",
        semester_plans=[
            SemesterPlan(
                term=p["term"],
                courses=p["courses"],
                total_credits=p["total_credits"],
                rationale=p.get("rationale", ""),
            )
            for p in override_result["semester_plans"]
        ],
        summary="",
        warnings=override_result["warnings"],
    )
    result = await orchestrate(
        req.query, student, program, current_pathway, programs, engine, _llm()
    )
    # Pre-validate each proposed op so the client can show accept/reject markers
    validated = []
    plan_state = {"semester_plans": override_result["semester_plans"]}
    for op in result.get("operations", []):
        check = validate_operation(op, plan_state, program, student, engine, programs)
        validated.append({
            "op": op,
            "ok": check.ok,
            "error": check.error,
            "description": describe_op(op, engine.courses),
        })
    result["validated"] = validated
    return result


class ExplainRequest(BaseModel):
    student_id: str
    prefs_override: Optional[dict[str, Any]] = None
    pathway_overrides: list[dict[str, Any]] = []


@app.post("/agents/explain")
async def explain_endpoint(req: ExplainRequest):
    _, programs, _ = _load_data()
    engine = _engine()
    base_student = _student_by_id(req.student_id)
    student = _apply_prefs_override(base_student, req.prefs_override)
    program = _program_by_id(student.program_id)
    recommender = PathwayRecommender(program, engine)
    base_pathway = recommender.generate_pathway(student)
    override_result = apply_overrides(
        base_pathway, req.pathway_overrides, program, student, engine, programs
    )
    plan_text = "\n".join(
        f"  {p['term']} ({p['total_credits']:.0f} cr): {', '.join(p['courses'])}"
        for p in override_result["semester_plans"]
    )
    system = (
        "You are a warm academic advisor explaining a recommended course plan to a "
        "student. Be specific, reference actual course names and prereq reasoning. "
        "3-4 short paragraphs. Do not invent courses."
    )
    user = (
        f"Student: {student.name}\n"
        f"Program: {program.name}\n"
        f"Interests: {', '.join(student.preferences.interests) or 'core progression'}\n"
        f"Concentration: {student.preferences.concentration_choice or 'none selected'}\n"
        f"Target graduation: {student.target_graduation}\n"
        f"Credit cap per term: {student.preferences.max_credits_per_semester}\n\n"
        f"Recommended plan:\n{plan_text}\n\n"
        "Explain why this plan makes sense."
    )
    resp = await _llm().complete(system, user, max_tokens=700)
    return {
        "text": resp.text,
        "provider": resp.provider,
        "is_template": resp.is_template,
    }


@app.post("/agents/advisor-summary")
async def advisor_summary_endpoint(req: ExplainRequest):
    _, programs, _ = _load_data()
    engine = _engine()
    base_student = _student_by_id(req.student_id)
    student = _apply_prefs_override(base_student, req.prefs_override)
    program = _program_by_id(student.program_id)
    recommender = PathwayRecommender(program, engine)
    base_pathway = recommender.generate_pathway(student)
    override_result = apply_overrides(
        base_pathway, req.pathway_overrides, program, student, engine, programs
    )
    plan_text = "\n".join(
        f"  {p['term']} ({p['total_credits']:.0f} cr): {', '.join(p['courses'])}"
        for p in override_result["semester_plans"]
    )
    system = (
        "You are drafting an advisor memo. Sections: STUDENT, PROGRAM, RECOMMENDATION, "
        "RATIONALE, RISKS/NOTES. Under 300 words, factual, professional, no emojis."
    )
    user = (
        f"Student: {student.name} ({student.student_id})\n"
        f"Program: {program.name}\n"
        f"Concentration: {student.preferences.concentration_choice or 'none'}\n"
        f"Current: {student.current_semester} | Target grad: {student.target_graduation}\n"
        f"GPA: {student.gpa} | Interests: {', '.join(student.preferences.interests) or 'n/a'}\n\n"
        f"Recommended plan:\n{plan_text}\n\n"
        + (
            f"Warnings: {'; '.join(override_result['warnings'])}"
            if override_result["warnings"]
            else ""
        )
    )
    resp = await _llm().complete(system, user, max_tokens=700)
    return {
        "text": resp.text,
        "provider": resp.provider,
        "is_template": resp.is_template,
    }


class ChatRequest(BaseModel):
    student_id: str
    question: str
    history: list[dict[str, str]] = []
    prefs_override: Optional[dict[str, Any]] = None
    pathway_overrides: list[dict[str, Any]] = []


@app.post("/agents/chat")
async def chat_endpoint(req: ChatRequest):
    _, programs, _ = _load_data()
    engine = _engine()
    base_student = _student_by_id(req.student_id)
    student = _apply_prefs_override(base_student, req.prefs_override)
    program = _program_by_id(student.program_id)
    recommender = PathwayRecommender(program, engine)
    base_pathway = recommender.generate_pathway(student)
    override_result = apply_overrides(
        base_pathway, req.pathway_overrides, program, student, engine, programs
    )
    plan_text = "\n".join(
        f"  {p['term']}: {', '.join(p['courses'])}"
        for p in override_result["semester_plans"]
    )
    concentration = student.preferences.concentration_choice or "none selected"
    interests = ", ".join(student.preferences.interests) or "none specified"
    system = (
        f"You are an academic advisor for {program.name} at NYIT advising {student.name}. "
        "Answer concisely (2-4 sentences unless asked for detail). Reference real NYIT "
        "course codes only. Do not invent courses.\n\n"
        f"Student profile:\n"
        f"  Concentration: {concentration}\n"
        f"  Interests: {interests}\n"
        f"  Max credits/semester: {student.preferences.max_credits_per_semester}\n"
        f"  Target graduation: {student.target_graduation}\n\n"
        f"Student's current pathway:\n{plan_text}"
    )
    history_text = "\n".join(
        f"{h['role']}: {h['content']}" for h in req.history[-6:]
    )
    user = f"{history_text}\n\nQuestion: {req.question}" if history_text else req.question
    resp = await _llm().complete(system, user, max_tokens=500)
    return {
        "text": resp.text,
        "provider": resp.provider,
        "is_template": resp.is_template,
    }
