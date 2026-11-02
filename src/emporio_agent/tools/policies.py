"""Policy lookup tool (BM25 over the manual's sections)."""
from functools import lru_cache

from ..retrieval.policy_search import PolicySearch


@lru_cache(maxsize=1)
def _search() -> PolicySearch:
    return PolicySearch()


def search_policies(query: str, top_k: int = 2) -> dict:
    hits = _search().search(query, top_k=max(1, min(int(top_k), 3)))
    if not hits:
        return {"found": False,
                "message": "Nada encontrado no manual. Não invente: ofereça encaminhar a um atendente."}
    return {"found": True,
            "sections": [{"section": h.section, "title": h.title, "text": h.text} for h in hits]}