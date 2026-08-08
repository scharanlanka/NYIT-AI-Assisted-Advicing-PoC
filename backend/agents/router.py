"""
Router Agent — classifies user intent into one of five categories.

Small, focused prompt. Fast + cheap. Its only job is to pick the right
specialist. Includes explicit rules for speculative-language handling.
"""
from __future__ import annotations

from typing import Any

from ..llm_service import LLMService, LLMResponse


async def router_agent(
    query: str,
    ctx: dict[str, Any],
    llm: LLMService,
) -> dict[str, Any]:
    program = ctx["program"]
    student = ctx["student"]
    concentration_names = ", ".join(c["name"] for c in program["concentrations"]) or "(none formally defined)"
    system = f"""You classify user requests for an academic advising system into ONE category.

Categories:
- PLAN_MOVE: user wants to move, add, remove, or swap specific courses in the plan
  Examples:
    - "move CSCI 465 to Fall 2027"
    - "drop the algorithms course"
    - "add data mining to spring"
- CONCENTRATION: user wants to change or explore concentration / track / specialization / focus area
  Examples:
    - "switch to cybersecurity"
    - "I'm more interested in data science now"
    - "I am thinking to move to AI as my concentration"  <-- speculative language still routes here
    - "let me focus on security instead"
    - "I want to focus on machine learning"
    - "could I explore the AI track"
- PREFERENCES: user wants to change credit cap, schedule preference, or general interests — NOT concentration
  Examples:
    - "cap me at 12 credits"
    - "prefer evening classes"
    - "add cybersecurity to my interests"
- QUESTION: user is asking a factual/explanatory question and does NOT express a desire to change anything
  Examples:
    - "what's the prereq for CSCI 465"
    - "why is this course in fall"
    - "how does the concentration work"
    - "what courses count toward AI"
- CLARIFICATION_NEEDED: request is genuinely too ambiguous even for a specialist to act on

DECISION RULES (in priority order):
1. Route based on user INTENT, not on program feasibility. Even if you think the program has no concentrations, "I want to switch to X concentration" is still CONCENTRATION — the specialist agent handles the "no such concentration" case gracefully.
2. Speculative or exploratory phrasing ("I am thinking of...", "could I...", "what if I...", "considering...") still routes to a change category if the user is expressing a WANT or DESIRE about their plan/prefs/concentration.
3. Words that signal QUESTION intent: "what", "how", "why", "explain", "which", "is there", "does" (in interrogative form). But if these appear alongside "I want to change X", still route to a change category.
4. If the query mentions a subject area (AI, machine learning, security, data, networking, etc.) AND expresses interest/desire in shifting focus toward it, route to CONCENTRATION.

Program context:
- Program: {program["name"]}
- Current concentration: {student["concentration"] or "not chosen"}
- Available concentrations: {concentration_names}

Output ONLY a JSON object (no prose, no markdown):
{{"intent": "CATEGORY", "confidence": 0.0-1.0, "note": "one sentence reason"}}"""

    result = await llm.complete_json(system, query, max_tokens=200)
    if not result.ok:
        return {
            "intent": "CLARIFICATION_NEEDED",
            "confidence": 0.0,
            "note": "Router response was not valid JSON",
        }
    return result.data
