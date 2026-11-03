"""Command-line chat with the Empório da Música agent."""
from .agent import Agent
from .config import get_settings
from .llm import get_client


def main() -> None:
    settings = get_settings()
    agent = Agent(client=get_client(), model=settings.model, today=settings.as_of_date)
    print(f"Empório da Música — atendimento (data de referência: {settings.as_of_date})")
    print("Digite 'sair' para encerrar.\n")
    while True:
        try:
            text = input("Você: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text.lower() in {"sair", "exit", "quit"}:
            break
        if not text:
            continue
        print(f"\nAgente: {agent.chat(text)}")
        print(f"  [tools usadas: {agent.trace}]\n")


if __name__ == "__main__":
    main()