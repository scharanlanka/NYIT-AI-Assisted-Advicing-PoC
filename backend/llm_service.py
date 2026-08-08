"""
LLM service for the advising POC.

- Async (compatible with FastAPI async endpoints)
- Works out-of-the-box with NO API keys — falls back to template responses
- Auto-detects Anthropic → OpenAI → template
- Provides both text (.complete) and JSON-parsed (.complete_json) helpers
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class LLMResponse:
    text: str
    provider: str
    is_template: bool = False


@dataclass
class JSONResult:
    ok: bool
    data: Any = None
    error: str = ""
    raw: str = ""


class LLMService:
    def __init__(self, provider: Optional[str] = None):
        forced = os.getenv("LLM_PROVIDER")
        chosen: str
        if provider:
            chosen = provider
        elif forced in ("anthropic", "openai", "template"):
            chosen = forced
        elif os.getenv("ANTHROPIC_API_KEY"):
            chosen = "anthropic"
        elif os.getenv("OPENAI_API_KEY"):
            chosen = "openai"
        else:
            chosen = "template"
        self.provider = chosen
        self._client = self._make_client()

    def _make_client(self) -> Any:
        if self.provider == "anthropic":
            try:
                import anthropic  # type: ignore
                return anthropic.Anthropic()
            except Exception:
                self.provider = "template"
                return None
        if self.provider == "openai":
            try:
                from openai import OpenAI  # type: ignore
                return OpenAI()
            except Exception:
                self.provider = "template"
                return None
        return None

    async def complete(
        self, system: str, user: str, max_tokens: int = 800
    ) -> LLMResponse:
        """Async wrapper around sync SDK calls via to_thread."""
        if self.provider == "anthropic" and self._client is not None:
            def _call():
                msg = self._client.messages.create(
                    model="claude-sonnet-4-5",
                    max_tokens=max_tokens,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                )
                return "".join(
                    b.text for b in msg.content if getattr(b, "type", "") == "text"
                )
            try:
                text = await asyncio.to_thread(_call)
                return LLMResponse(text=text.strip(), provider="anthropic")
            except Exception as e:
                return LLMResponse(
                    text=f"[LLM error: {e}]", provider="anthropic-error", is_template=True
                )
        if self.provider == "openai" and self._client is not None:
            def _call():
                comp = self._client.chat.completions.create(
                    model="gpt-4o-mini",
                    max_tokens=max_tokens,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                )
                return comp.choices[0].message.content
            try:
                text = await asyncio.to_thread(_call)
                return LLMResponse(text=text.strip(), provider="openai")
            except Exception as e:
                return LLMResponse(
                    text=f"[LLM error: {e}]", provider="openai-error", is_template=True
                )
        return LLMResponse(text="", provider="template", is_template=True)

    async def complete_json(
        self, system: str, user: str, max_tokens: int = 500
    ) -> JSONResult:
        """Get a JSON response and parse it, stripping markdown fences."""
        resp = await self.complete(system, user, max_tokens=max_tokens)
        if resp.is_template or not resp.text:
            return JSONResult(ok=False, error="template mode / empty", raw=resp.text)
        raw = resp.text.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw)
        cleaned = re.sub(r"```\s*$", "", cleaned).strip()
        try:
            data = json.loads(cleaned)
            return JSONResult(ok=True, data=data, raw=raw)
        except Exception as e:
            return JSONResult(ok=False, error=str(e), raw=raw)
