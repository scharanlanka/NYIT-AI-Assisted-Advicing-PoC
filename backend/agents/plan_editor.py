"""
Plan Editor Agent — proposes structured course-level operations.

Locked to the program universe. Every course reference is re-validated
downstream against the guardrails; this agent's job is only to translate
user intent into a well-formed operation list.
"""
from __future__ import annotations

from typing import Any

from llm_service import LLMService


async def plan_editor_agent(
    query: str,
    ctx: dict[str, Any],
    llm: LLMService,
) -> dict[str, Any]:
    program = ctx["program"]
    student = ctx["student"]
    universe = ", ".join(ctx["universe"])
    system = f"""You propose structured course-level changes to a student's plan.

Program: {program["name"]}
Current concentration: {student["concentration"] or "not chosen"}
Allowed courses (STRICTLY use only these — never any others):
{universe}

Current planned semesters:
{ctx["currentPlan"]}

Student current term: {student["currentTerm"]}

Output ONLY a JSON object:
{{
  "operations": [
    {{"type": "move", "course": "CSCI 465", "from_term": "Spring 2028", "to_term": "Fall 2027"}},
    {{"type": "remove", "course": "CSCI 460", "from_term": "Fall 2027"}},
    {{"type": "add", "course": "CSCI 470", "to_term": "Spring 2028"}}
  ],
  "reasoning": "brief explanation for the advisor"
}}

STRICT RULES:
1. ONLY use course IDs from the allowed list above. Never invent codes.
2. Never modify past or current term ({student["currentTerm"]}) — only future planned terms.
3. Term format: "Fall YYYY" or "Spring YYYY".
4. If the request is unclear or would break prereqs, return {{"operations": [], "reasoning": "explanation"}}.
5. No markdown, no backticks, no prose outside JSON."""

    result = await llm.complete_json(system, query, max_tokens=800)
    if not result.ok:
        return {
            "operations": [],
            "reasoning": f"Plan Editor could not parse response: {result.error}",
        }
    data = result.data
    return {
        "operations": data.get("operations", []) or [],
        "reasoning": data.get("reasoning", "") or "",
    }
