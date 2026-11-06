"""OpenAI-compatible adapter: any /chat/completions endpoint with native tool
calling (llama-server, vLLM, Ollama, OpenAI, Anthropic-shims, ...).

The model receives the full catalog as function tools plus a routing-only
instruction, and its tool_calls become the selection. Deterministic arguments
(e.g. resolved dates) are whatever the model emitted.

Env: ROUTEBENCH_BASE_URL, ROUTEBENCH_API_KEY, ROUTEBENCH_MODEL.
"""
from __future__ import annotations

import json
import os
from typing import Any

import httpx

from .base import RoutingRequest, SelectedTool, Selection

SYSTEM = (
    "You are a tool-routing decision module. Given the user's request, choose "
    "which tools should be exposed to handle it. Do NOT answer the request "
    "yourself and do NOT invent tool names: pick only from the provided tools. "
    "If no tool applies, reply with a short plain-text message and no tool call. "
    "Fill tool arguments only when the request states the values; use the "
    "current date/time given in the user message when a time argument is needed."
)


class OpenAICompatAdapter:
    name = "openai-compat"

    def __init__(self, *, base_url: str | None = None, api_key: str | None = None,
                 model: str | None = None, temperature: float = 0.0, timeout: float = 120.0,
                 max_tokens: int = 512):
        self.base_url = (base_url or os.environ.get("ROUTEBENCH_BASE_URL", "http://127.0.0.1:8080/v1")).rstrip("/")
        self.api_key = api_key or os.environ.get("ROUTEBENCH_API_KEY", "none")
        self.model = model or os.environ.get("ROUTEBENCH_MODEL", "")
        self.temperature = temperature
        self.timeout = timeout
        self.max_tokens = max_tokens

    def _tools_payload(self, catalog) -> list[dict[str, Any]]:
        return [{
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("parameters") or {"type": "object", "properties": {}},
            },
        } for t in catalog]

    def select(self, request: RoutingRequest) -> Selection:
        user = request.query
        if request.now is not None:
            user = f"[current time: {request.now.isoformat()}]\n{user}"
        messages = [{"role": "system", "content": SYSTEM}]
        for turn in request.history:
            role = turn.get("role", "user")
            content = turn.get("content", turn.get("query", ""))
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": str(content)})
        messages.append({"role": "user", "content": user})

        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model or "local",
                "messages": messages,
                "tools": self._tools_payload(request.catalog),
                "tool_choice": "auto",
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        msg = resp.json()["choices"][0]["message"]
        calls = msg.get("tool_calls") or []
        tools: list[SelectedTool] = []
        valid = {t["name"] for t in request.catalog}
        for call in calls:
            fn = call.get("function", {})
            name = fn.get("name", "")
            if name not in valid:
                continue  # hallucinated tool names count as noise, not as a tool
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            if not isinstance(args, dict):
                args = {}
            tools.append(SelectedTool(name=name, arguments=args))
        return Selection(tools=tuple(tools[: request.max_tools]))
