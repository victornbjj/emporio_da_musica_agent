"""Catalog queries: availability, active promotions, search and alternatives.

The LLM never touches the DataFrames. It calls tools that call this class, so
business rules (availability, promotions, PIX) are always applied in code.
"""
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from functools import lru_cache

from ..retrivel.policy_search import  STOPWORDS
from ..rules.pricing import (
    active_promotion_percent, allowed_installments, format_brl, quote_price,
)
from .loader import load_all

MAX_RESULTS = 8


def _stem(token: str) -> str:
    """Rough PT stemmer: 'violões'/'violão' -> same stem; plural 's' dropped."""
    if token.endswith(("oes", "aes")):          # violoes -> violao
        token = token[:-3] + "ao"
    elif len(token) > 4 and token.endswith("s"):
        token = token[:-1]
    return token[:5] if token.isalpha() else token


def _tokens(text) -> list[str]:
    text = unicodedata.normalize("NFKD", str(text).lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return [_stem(t) for t in re.findall(r"[a-z0-9]+", text) if t not in STOPWORDS]



ACESSORY_TOKEN = {
    _stem(w) for w in (
        "corda", "cordas", "palheta", "palhetas", "cabo", "cabos", "pedal", "pedais",
        "amplificador", "amplificadores", "case", "cases", "afinador", "capa", "capas",
    )
}


def _availability(status: str, stock: int) -> str:
    if status == "active":
        return "available" if stock > 0 else "out_of_stock"

    return status


class Catalog:
    def __init__(self, data: dict):
        cats = data["categories"]
        self.cat_name = dict(zip(cats.category_id, cats.name))
        self._cat_name_tokens = {c: set(_tokens(n)) for c, n in self.cat_name.items()}

        self._cat_desc_tokens = {
        c: set(_tokens(d)) for c, d in zip(cats.category_id, cats.description)
         }
        promos = data["promotions"]
        self.rows: list[dict] = []
        for r in data["products"].itertuples():
            promo = active_promotion_percent(promos, r.product_id)
            quote = quote_price(r.price_brl, promo)
            self.rows.append({
                "product_id": int(r.product_id),
                "name" : r.name,
                "category_id" : int(r.category_id),
                "category" : self.cat_name.get(r.category_id, ""),
                "description" :  r.description,
                "specs" : r.specs,
                "availability" : _availability(r.status, r.stock_quantity),
                "quote": quote,
                "name_tokens": set(_tokens(r.name)),
                "all_tokens": set(_tokens(f"{r.name} {r.description} {' '.join(map(str, r.specs.values()))}""")),


            })


    def is_accessory_request(self, text: str) -> bool:
        tokens = set(_tokens(text))
        if "orque" in tokens:
            tokens.discard(_stem("cordas"))
        return bool(tokens & ACESSORY_TOKEN)

    def resolve_categories(self, text: str) -> list[int]:
        """Match by category name first; fall back to the category description."""
        tokens = set(_tokens(text))
        by_name = [c for c, t in self._cat_name_tokens.items() if tokens & t]
        if by_name:
            return by_name
        return [c for c, t in self._cat_desc_tokens.items() if tokens & t]

    def category_names(self, ids: list[int]) -> list[str]:
        return [self.cat_name[c] for c in ids]

    """views for the LLM"""
    @staticmethod
    def summary(row: dict) -> dict:
        q = row["quote"]
        return {
            "product_id": row["product_id"],
            "name": row["name"],
            "category": row["category"],
            "availability": row["availability"],
            "list_price": format_brl(q.original),
            "promo_percent": q.promo_percent,
            "price_to_pay": format_brl(q.final_price),
            "pix_price": format_brl(q.pix_price) if q.pix_price is not None else None,
        }


    def details(self, row: dict) -> dict:
        out= self.summary(row)
        out["description"] = row["description"]
        out["specs"] = row["specs"]
        if row["availability"] == "available":
            options = allowed_installments(row["quote"].final_price)
            if options:
                n, per = options[-1]
                out["max_installments"] = f"até {n}x de {format_brl(per)} sem juros"
        return out

    # ---------- queries ----------


    def find_by_name(self, text :str) -> list[dict]:
        """Products whose NAME contains all words of `text` (best partial match otherwise) ."""

        tokens = set(_tokens(text))
        if not tokens:
            return []

        scored = [(len(tokens & r["name_tokens"]), r) for r in self.rows]
        best = max((s for s, r in scored), default=0)
        if best == 0 or best < len(tokens):
            return []
        return [r for s, r in scored if s == best]


    def alternatives(self, row: dict, n : int =3) -> list[dict]:
        """Available products from the same category, closest in price. """

        target = row["quote"].final_price
        same = [
            r for r in self.rows
            if r["category_id"] == row["category_id"]
            and r["product_id"] != row["product_id"]
            and r["availability"] == "available"
        ]

        same.sort(
            key= lambda r: abs(r["quote"].final_price - target),
        )

        return same[:n]

    def search(self, category=None, query=None, min_price=None, max_price=None,
               only_available=True, sort="price_asc", limit=5) -> dict:
        if self.is_accessory_request(f"{category or ''} {query or ''}"):
            return {"out_of_scope": "accessories", "count": 0, "products": []}

        rows = self.rows
        if category:
            ids = self.resolve_categories(category)
            if not ids:
                return {"category_not_found": category, "count": 0, "products": [],
                        "valid_categories": sorted(set(self.cat_name.values()))}
            rows = [r for r in rows if r["category_id"] in ids]
            if not rows:
                return {"empty_category": self.category_names(ids), "count": 0, "products": []}

        try:
            lo = Decimal(str(min_price)) if min_price is not None else None
            hi = Decimal(str(max_price)) if max_price is not None else None
        except InvalidOperation:
            return {"error": "min_price and max_price must be numbers", "count": 0, "products": []}
        # Price filters use the price the customer would PAY (promotion applied).
        if lo is not None:
            rows = [r for r in rows if r["quote"].final_price >= lo]
        if hi is not None:
            rows = [r for r in rows if r["quote"].final_price <= hi]

        if query:
            q = set(_tokens(query))
            if q:
                scored = [(len(q & r["all_tokens"]), r) for r in rows]
                best = max((s for s, _ in scored), default=0)
                rows = [r for s, r in scored if s == best and best > 0]

        unavailable = [r for r in rows if r["availability"] != "available"]
        if only_available:
            rows = [r for r in rows if r["availability"] == "available"]

        rows = sorted(rows, key=lambda r: r["quote"].final_price, reverse=(sort == "price_desc"))
        limit = max(1, min(int(limit), MAX_RESULTS))
        result = {
            "count": len(rows),
            "shown": min(len(rows), limit),
            "products": [self.summary(r) for r in rows[:limit]],
        }
        if only_available and unavailable:
            result["unavailable_matches"] = len(unavailable)
        return result

@lru_cache(maxsize=1)
def get_catalog() -> Catalog:
    return Catalog(load_all())
