"""Hand-written function-calling loop (no agent framework)."""
import json
import os
import time
from dataclasses import dataclass
from datetime import date

from openai import BadRequestError, RateLimitError

from .config import get_as_of_date, get_settings
from .prompts import build_system_prompt
from .tools.registry import TOOL_SCHEMAS, dispatch

MAX_TOOL_ROUNDS = 5       # tool-call rounds allowed per customer message
MAX_HISTORY_TURNS = 6     # customer messages kept in context (Groq: ~8K tokens/min)
MAX_RETRIES = 3
FALLBACK = ("Desculpa, tive um problema aqui para consultar o sistema. "
            "Pode repetir ou tentar de novo em instantes?")


@dataclass
class ToolTrace:
    name: str
    arguments: str
    result: dict


def _retry_delay(exc: Exception, attempt: int) -> float:
    try:
        return min(max(float(exc.response.headers["retry-after"]), 1.0), 20.0)
    except (AttributeError, KeyError, TypeError, ValueError):
        return float(2 ** (attempt + 1))     # 2s, 4s, 8s


class Agent:
    def __init__(self, client=None, model: str | None = None,
                 today: date | None = None, sleep=time.sleep):
        if client is None:
            from .llm import get_client
            client = get_client()
        self.client = client
        self.model = model or get_settings().model
        self.sleep = sleep
        self.messages: list[dict] = [
            {"role": "system", "content": build_system_prompt(today or get_as_of_date())}
        ]
        self.trace: list[ToolTrace] = []     # tools used in the last turn (for the examples)

    # ---------- public ----------
    def chat(self, user_text: str) -> str:
        self.trace = []
        self.messages.append({"role": "user", "content": user_text})
        self._trim()
        try:
            for _ in range(MAX_TOOL_ROUNDS):
                message = self._complete()
                if not message.tool_calls:
                    return self._finish((message.content or "").strip() or FALLBACK)
                self.messages.append(self._assistant_tool_message(message))
                for call in message.tool_calls:
                    result = dispatch(call.function.name, call.function.arguments)
                    self.trace.append(ToolTrace(call.function.name, call.function.arguments, result))
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(result, ensure_ascii=False, default=str),
                    })
        except (RateLimitError, BadRequestError):
            pass                              # retries exhausted: apologize instead of crashing
        return self._finish(FALLBACK)         # also reached when MAX_TOOL_ROUNDS is exceeded

    # ---------- internals ----------
    def _finish(self, reply: str) -> str:
        self.messages.append({"role": "assistant", "content": reply})
        return reply

    @staticmethod
    def _assistant_tool_message(message) -> dict:
        # Rebuilt by hand: provider-specific extra fields (e.g. reasoning) must not be echoed back.
        return {
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": [
                {"id": c.id, "type": "function",
                 "function": {"name": c.function.name, "arguments": c.function.arguments or "{}"}}
                for c in message.tool_calls
            ],
        }

    def _complete(self):
        kwargs = {"model": self.model, "messages": self.messages,
                  "tools": TOOL_SCHEMAS, "temperature": 0.2}
        effort = os.getenv("LLM_REASONING_EFFORT")       # optional, e.g. "low" for gpt-oss
        if effort:
            kwargs["extra_body"] = {"reasoning_effort": effort}

        for attempt in range(MAX_RETRIES + 1):
            try:
                return self.client.chat.completions.create(**kwargs).choices[0].message
            except RateLimitError as exc:
                if attempt == MAX_RETRIES:
                    raise
                self.sleep(_retry_delay(exc, attempt))
            except BadRequestError as exc:
                # gpt-oss sometimes emits a malformed tool call; asking again usually works.
                if "tool_use_failed" not in str(exc) or attempt == MAX_RETRIES:
                    raise

    def _trim(self) -> None:
        """Keep the system prompt plus the last N customer turns (never cuts a tool exchange)."""
        users = [i for i, m in enumerate(self.messages) if m["role"] == "user"]
        if len(users) > MAX_HISTORY_TURNS:
            cut = users[-MAX_HISTORY_TURNS]
            self.messages = [self.messages[0]] + self.messages[cut:]