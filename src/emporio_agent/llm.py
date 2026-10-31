from openai import OpenAI

from .config import get_settings


def get_client() -> OpenAI:
    s = get_settings()
    return OpenAI(api_key=s.api_key, base_url=s.base_url)


def smoke_test() -> None:
    s = get_settings()
    client = get_client()
    print(f"Model: {s.model} @ {s.base_url}")

    r = client.chat.completions.create(
        model=s.model,
        messages=[{"role": "user", "content": "Responda apenas: conexão ok."}],
    )
    print("Chat:", r.choices[0].message.content)

    tools = [{
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get weather for a city",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            },
        },
    }]
    r = client.chat.completions.create(
        model=s.model,
        messages=[{"role": "user", "content": "Qual o clima em Campo Grande?"}],
        tools=tools,
    )
    calls = r.choices[0].message.tool_calls
    print("Tool calling:", f"OK -> {calls[0].function.name}" if calls else "NOT triggered")


if __name__ == "__main__":
    smoke_test()