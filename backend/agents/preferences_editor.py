"""
Preferences Editor Agent — handles preference-level changes.

Has full concentration definitions with member courses so it can do fuzzy
matching ("cybersecurity" → "Network Security"). Falls back gracefully to
change_interests when a program has no formal concentrations.
"""
from __future__ import annotations

from typing import Any

from ..llm_service import LLMService


async def preferences_editor_agent(
    query: str,
    ctx: dict[str, Any],
    llm: LLMService,
) -> dict[str, Any]:
    program = ctx["program"]
    student = ctx["student"]
    concentration_lines = []
    for c in program["concentrations"]:
        preview_courses = c["courses"][:10]
        preview = ", ".join(preview_courses)
        if len(c["courses"]) > 10:
            preview += ", ..."
        line = f"  - {c['name']}"
        if c.get("description"):
            line += f": {c['description']}"
        line += f"\n    Courses: {preview or '(flexible)'}"
        concentration_lines.append(line)
    concentration_details = "\n".join(concentration_lines) or "  (this program does NOT have formal concentrations)"
    has_formal = bool(program["concentrations"])

    system = f"""You handle preference changes for a student — concentration, credit cap, schedule, or interests.

Program: {program["name"]}
Student's current preferences:
- Concentration: {student["concentration"] or "not chosen"}
- Credit cap per term: {student["maxCredits"]}
- Schedule: {student["schedule"]}
- Interests: {", ".join(student["interests"]) or "none stated"}

Available concentrations in {program["id"]}:
{concentration_details}

Common concentration name mappings (match user requests to actual names):
- "cybersecurity" / "cyber" / "security" → "Network Security" (if available in this program)
- "AI" / "ML" / "machine learning" → "Artificial Intelligence" (if available)
- "data" / "analytics" / "big data" → "Big Data Management and Analytics" or "Data Science" (if available)
- "general" / "no concentration" → "General Option" (if available)

Related interest keywords for graceful fallback (use when no matching concentration exists):
- AI-themed → ["artificial intelligence", "machine learning", "deep learning"]
- Security-themed → ["cybersecurity", "network security", "information security"]
- Data-themed → ["data science", "big data", "analytics"]
- Systems-themed → ["operating systems", "distributed systems", "networks"]

Output ONLY a JSON object:
{{
  "operations": [
    {{"type": "change_concentration", "concentration": "Network Security"}},
    {{"type": "change_credits", "value": 12}},
    {{"type": "change_schedule", "value": "evening"}},
    {{"type": "change_interests", "value": ["cybersecurity", "networks"]}}
  ],
  "reasoning": "brief explanation of what will change and downstream implications"
}}

STRICT RULES:
1. For change_concentration, use the EXACT concentration name from the available list.
2. Match user requests loosely — "cybersecurity" should map to "Network Security" if available.
3. For change_credits, value must be 6-18.
4. For change_schedule, value must be "morning" | "afternoon" | "evening" | "no_preference".
5. GRACEFUL FALLBACK when no matching concentration exists:
   - If this program has NO formal concentrations at all ({"N/A here" if has_formal else "which is the case"}), do NOT return empty operations. Instead propose change_interests with the related keywords above so the recommender biases the plan toward the requested theme. Explain in reasoning.
   - If this program HAS concentrations but none matches the request, list available names in reasoning and return empty operations.
6. Multiple operations allowed.
7. No markdown, just JSON."""

    result = await llm.complete_json(system, query, max_tokens=500)
    if not result.ok:
        return {
            "operations": [],
            "reasoning": f"Preferences Editor could not parse response: {result.error}",
        }
    data = result.data
    return {
        "operations": data.get("operations", []) or [],
        "reasoning": data.get("reasoning", "") or "",
    }
