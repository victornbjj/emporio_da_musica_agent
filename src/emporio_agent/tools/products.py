"""Product tools exposed to the LLM. Return plain JSON-serializable dicts."""
from ..data.repository import get_catalog


def search_products(category: str | None = None, query: str | None = None,
                    min_price: float | None = None, max_price: float | None = None,
                    only_available: bool = True, sort: str = "price_asc",
                    limit: int = 5) -> dict:
    """Search the catalog with structured filters (prices are what the customer pays)."""

    return get_catalog().search(category, query, min_price, max_price, only_available, sort, limit)

def get_product_details(name: str) ->  dict:

    cat = get_catalog()
    if cat.is_accessory_request(name):
        return {"found": False, "out_of_scope": "accessories"}

    matches = cat.find_by_name(name)
    if not matches:
        return {"found": False, "message": "No product with that name in the catalog."}

    if len(matches) > 1:
        return {"found": True, "ambiguous": True,
                "matches": [cat.summary(r) for r in matches[:5]]}

    row = matches[0]
    out = {"found": True, "product": cat.details(row)}
    if row["availability"] != "available":
        out["alternatives"] = [cat.summary(r) for r in cat.alternatives(row)]
    return out