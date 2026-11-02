"""BM25 search over the policy chunks (Portuguese, accent-insensitive)."""
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from rank_bm25 import BM25Okapi

from ..config import RAW_DATA_DIR
from .chunker import Chunk, chunk_policies

STOPWORDS = {
    "a", "o", "as", "os", "um", "uma", "de", "da", "do", "das", "dos", "em", "no", "na",
    "nos", "nas", "por", "para", "com", "sem", "e", "ou", "que", "se", "ao", "aos", "eu",
    "voce", "voces", "meu", "minha", "posso", "pode", "quero", "qual", "quais", "como",
    "quanto", "quantos", "sao", "ser", "tem", "ter", "mais", "mas", "foi", "vai",
}


def tokenize(text: str) -> list[str]:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    tokens = [t for t in re.findall(r"[a-z0-9]+", text) if t not in STOPWORDS]
    # "10x", "3x", "12x" all mean installments: map them to the stem of "parcelamento".
    tokens = ["parcelamento" if re.fullmatch(r"\d+x", t) else t for t in tokens]
    # Crude stemming: keep the first 5 letters so "devolver"/"devolucao" both -> "devol".
    return [t[:5] if t.isalpha() else t for t in tokens]


@dataclass(frozen=True)
class PolicyHit:
    section: str
    title: str
    text: str
    score: float


class PolicySearch:
    def __init__(self, pdf_path: Path | None = None):
        self.chunks: list[Chunk] = chunk_policies(pdf_path or RAW_DATA_DIR / "politicas_da_loja.pdf")
        # Parent + title give context; the title is repeated so heading words weigh more.
        docs = [tokenize(f"{c.parent} {c.title} {c.title} {c.text}") for c in self.chunks]
        self._bm25 = BM25Okapi(docs)

    def search(self, query: str, top_k: int = 2) -> list[PolicyHit]:
        tokens = tokenize(query)
        if not tokens:
            return []
        scores = self._bm25.get_scores(tokens)
        ranked = sorted(zip(scores, self.chunks), key=lambda p: p[0], reverse=True)
        return [
            PolicyHit(c.section, c.title, c.text, round(float(s), 2))
            for s, c in ranked[:top_k]
            if s > 0
        ]