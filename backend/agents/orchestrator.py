"""
Orchestrator — the entry point for the multi-agent system.

Routes the query through router → specialist chain and returns a unified
response with routing metadata. Low-confidence handoff: if the router
returns a confidence below the threshold, surface uncertainty instead of
committing to a wrong specialist.
"""
from __future__ import annotations

from typing import Any

from ..llm_service import LLMService
from ..models import Pathway, Program, Student
from ..prerequisite_engine import PrerequisiteEngine
from .context import build_curriculum_context
from .plan_editor import plan_editor_agent
from .preferences_editor import preferences_editor_agent
from .qa import qa_agent
from .router import router_agent


LOW_CONFIDENCE_THRESHOLD = 0.6


async def orchestrate(
    query: str,
    student: Student,
    program: Program,
    pathway: Pathway,
    programs: dict[str, Program],
    engine: PrerequisiteEngine,
    llm: LLMService,
) -> dict[str, Any]:
    ctx = build_curriculum_context(student, program, pathway, programs, engine)
    routing = await router_agent(query, ctx, llm)

    # Low-confidence fallback
    conf = routing.get("confidence", 0)
    intent = routing.get("intent", "CLARIFICATION_NEEDED")
    if conf < LOW_CONFIDENCE_THRESHOLD and intent != "CLARIFICATION_NEEDED":
        return {
            "routing": routing,
            "agent": "(low-confidence handoff)",
            "operations": [],
            "reasoning": (
                f"Router isn't confident ({round(conf * 100)}%) about how to handle this. "
                f"It's leaning toward {intent} but the phrasing is ambiguous. "
                f"Could you rephrase? For example: 'change my concentration to X' or "
                f"'add course Y to fall 2027' or 'what prereqs does Z need?'"
            ),
            "is_answer": True,
        }

    if intent == "PLAN_MOVE":
        agent = "Plan Editor Agent"
        result = await plan_editor_agent(query, ctx, llm)
    elif intent in ("CONCENTRATION", "PREFERENCES"):
        agent = "Preferences Editor Agent"
        result = await preferences_editor_agent(query, ctx, llm)
    elif intent == "QUESTION":
        agent = "Q&A Agent"
        result = await qa_agent(query, ctx, llm)
    else:
        agent = "(clarification needed)"
        result = {
            "operations": [],
            "reasoning": routing.get("note")
            or "The request is ambiguous. Try being more specific about which course, term, or preference you'd like to change.",
            "is_answer": True,
        }

    return {"routing": routing, "agent": agent, **result}
