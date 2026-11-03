import json
from datetime import date
from types import SimpleNamespace

import httpx
from openai import BadRequestError, RateLimitError

from emporio_agent.agent import FALLBACK, MAX_HISTORY_TURNS, MAX_TOOL_ROUNDS, Agent
from emporio_agent.prompts import build_system_prompt

REQUEST = httpx.Request("POST", "https://example.test/v1/chat/completions")


def reply(content=None, tool_calls=None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def call(call_id, name, args):
    raw = args if isinstance(args, str) else json.dumps(args)
    return SimpleNamespace(id=call_id, type="function",
                           function=SimpleNamespace(name=name, arguments=raw))


class FakeClient:
    """Plays back scripted replies (or raises scripted errors); records every request."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def make_agent(client, sleeps=None):
    return Agent(client=client, model="fake", today=date(2026, 3, 31),
                 sleep=(sleeps.append if sleeps is not None else lambda s: None))


def rate_limit():
    return RateLimitError("rate limited", response=httpx.Response(429, request=REQUEST), body=None)


def bad_request(text):
    return BadRequestError(text, response=httpx.Response(400, request=REQUEST), body=None)


def roles(agent):
    return [m["role"] for m in agent.messages]


def test_direct_answer_without_tools():
    agent = make_agent(FakeClient([reply("Oi! Como posso ajudar?")]))
    assert agent.chat("oi") == "Oi! Como posso ajudar?"
    assert agent.trace == []
    assert roles(agent) == ["system", "user", "assistant"]


def test_finish_normalizes_special_characters():
    agent = make_agent(FakeClient([reply("e\u2011mail e R$\u202f1\u00a0000")]))
    assert agent.chat("qual seu e-mail?") == "e-mail e R$ 1 000"


def test_tool_call_round_trip():
    client = FakeClient([
        reply(tool_calls=[call("c1", "payment_options", {"amount": 500})]),
        reply("Dá para parcelar em até 5x."),
    ])
    agent = make_agent(client)
    assert agent.chat("posso parcelar R$ 500?") == "Dá para parcelar em até 5x."
    assert roles(agent) == ["system", "user", "assistant", "tool", "assistant"]
    assert agent.messages[2]["tool_calls"][0]["id"] == "c1"
    assert agent.messages[3]["tool_call_id"] == "c1" and "R$ 500,00" in agent.messages[3]["content"]
    assert agent.trace[0].name == "payment_options"
    assert client.calls[1]["messages"][-1]["role"] == "tool"      # LLM saw the tool result


def test_invalid_tool_arguments_do_not_break_the_loop():
    client = FakeClient([
        reply(tool_calls=[call("c1", "payment_options", {"campo_inventado": 1})]),
        reply("Me diz o valor que você quer parcelar?"),
    ])
    agent = make_agent(client)
    assert agent.chat("quero parcelar") == "Me diz o valor que você quer parcelar?"
    assert "error" in agent.trace[0].result


def test_tool_loop_is_capped():
    looping = [reply(tool_calls=[call(f"c{i}", "payment_options", {"amount": 100})])
               for i in range(MAX_TOOL_ROUNDS)]
    client = FakeClient(looping)
    agent = make_agent(client)
    assert agent.chat("x") == FALLBACK
    assert len(client.calls) == MAX_TOOL_ROUNDS
    assert agent.messages[-1] == {"role": "assistant", "content": FALLBACK}


def test_rate_limit_is_retried_with_waiting():
    sleeps = []
    agent = make_agent(FakeClient([rate_limit(), reply("ok")]), sleeps)
    assert agent.chat("oi") == "ok"
    assert len(sleeps) == 1


def test_rate_limit_exhausted_returns_apology_not_exception():
    agent = make_agent(FakeClient([rate_limit() for _ in range(4)]))
    assert agent.chat("oi") == FALLBACK
    assert roles(agent)[-2:] == ["user", "assistant"]


def test_malformed_tool_call_is_retried():
    client = FakeClient([bad_request("tool_use_failed: bad call"), reply("ok")])
    assert make_agent(client).chat("oi") == "ok"
    assert len(client.calls) == 2


def test_other_bad_requests_are_not_retried():
    client = FakeClient([bad_request("invalid model")])
    assert make_agent(client).chat("oi") == FALLBACK
    assert len(client.calls) == 1


def test_history_is_trimmed_without_orphaning_tool_messages():
    turns = MAX_HISTORY_TURNS + 3
    script = []
    for i in range(turns):
        script += [reply(tool_calls=[call(f"c{i}", "payment_options", {"amount": 100})]),
                   reply(f"resposta {i}")]
    agent = make_agent(FakeClient(script))
    for i in range(turns):
        agent.chat(f"pergunta {i}")
    assert roles(agent).count("user") == MAX_HISTORY_TURNS
    assert roles(agent)[0] == "system" and roles(agent)[1] == "user"


def test_prompt_contains_date_and_key_guardrails():
    p = build_system_prompt(date(2026, 3, 31))
    assert "31/03/2026" in p
    assert "NÃO vende acessórios" in p
    assert "4 últimos dígitos" in p
    assert "NUNCA informe preço" in p