import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path


from dotenv import load_dotenv

load_dotenv()

ROOT= Path(__file__).resolve().parents[2]
RAW_DATA_DIR = ROOT / 'data' / 'raw'

@dataclass(frozen=True)
class Settings:
    api_key: str
    base_url: str
    model: str
    as_of_date: date

def get_settings() -> Settings:
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        raise RuntimeError("LLM_API_KEY not set. Copy .env.example to .env.")
    return Settings(
        api_key=api_key,
        base_url=os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1"),
        model=os.getenv("LLM_MODEL_NAME", "openai/gpt-oss-120b"),
        as_of_date=get_as_of_date(),
    )


def get_as_of_date() -> date:
    return date.fromisoformat(os.getenv("AS_OF_DATE", "2026-03-31"))
