"""
Q&A Agent — answers questions grounded in the plan without proposing changes.
"""
from __future__ import annotations

from typing import Any

from ..llm_service import LLMService


async def qa_agent(
    query: str,
    ctx: dict[str, Any],
    llm: LLMService,
) -> dict[str, Any]:
    program = ctx["program"]
    student = ctx["student"]
    universe = ", ".join(ctx["universe"][:60])
    system = f"""You answer questions about a student's academic plan and NYIT curriculum. Do NOT propose changes.

Student: {student["name"]}
Program: {program["name"]}
Current concentration: {student["concentration"] or "not chosen"}
Current term: {student["currentTerm"]}

Current plan:
{ctx["currentPlan"]}

Available courses: {universe}{"..." if len(ctx["universe"]) > 60 else ""}

Answer concisely (2-4 sentences). Reference actual course codes only from the list. Do not invent courses. Do not propose plan changes."""

    resp = await llm.complete(system, query, max_tokens=400)
    return {
        "operations": [],
        "reasoning": resp.text,
        "is_answer": True,
    }
