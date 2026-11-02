import pytest

from emporio_agent.data.loader import load_all
from emporio_agent.data.repository import Catalog
from emporio_agent.rules.pricing import format_brl
from emporio_agent.tools.products import get_product_details, search_products


@pytest.fixture(scope="module")
def cat():
    return Catalog(load_all())


def test_format_brl():
    assert format_brl(1234.5) == "R$ 1.234,50"
    assert format_brl(599.9) == "R$ 599,90"


def test_only_active_with_stock_are_available(cat):
    avail = {r["product_id"] for r in cat.rows if r["availability"] == "available"}
    assert 96 not in avail      # active but stock 0
    assert 130 not in avail     # coming_soon (has stock)
    assert 136 not in avail     # discontinued (has stock)


def test_default_search_hides_unavailable(cat):
    ids = {p["product_id"] for p in cat.search(category="baixo", limit=8)["products"]}
    assert 136 not in ids and 135 in ids


def test_promotion_applied_and_pix_not_stacked(cat):
    p = cat.summary(next(r for r in cat.rows if r["product_id"] == 121))   # active 20%
    assert p["promo_percent"] == 20 and p["pix_price"] is None
    plain = cat.summary(next(r for r in cat.rows if r["product_id"] == 81))  # no promo
    assert plain["promo_percent"] is None and plain["pix_price"] is not None


def test_only_active_promotions_are_offered(cat):
    promos = load_all()["promotions"]
    for row in cat.rows:
        pid = row["product_id"]
        active = promos[(promos.product_id == pid) & promos.is_active]
        expected = int(active.discount_percent.max()) if not active.empty else None
        assert row["quote"].promo_percent == expected


def test_takamine_gd20_has_no_discount():
    p = get_product_details("Takamine GD20")["product"]
    assert p["promo_percent"] is None and p["price_to_pay"] == p["list_price"]


def test_price_filter_uses_price_to_pay(cat):
    row = next(r for r in cat.rows if r["product_id"] == 121)
    q = row["quote"]
    ids = {p["product_id"] for p in cat.search(max_price=float(q.final_price), limit=8)["products"]}
    assert 121 in ids and q.final_price < q.original


def test_accessories_are_out_of_scope():
    assert search_products(query="cordas para violão")["out_of_scope"] == "accessories"
    assert search_products(category="palhetas")["out_of_scope"] == "accessories"
    assert get_product_details("cabo para guitarra")["out_of_scope"] == "accessories"


def test_known_but_empty_categories():
    r = search_products(category="saxofone")
    assert r["count"] == 0 and r["empty_category"]
    assert search_products(category="cordas orquestrais")["empty_category"] == ["Cordas Orquestrais"]


def test_unknown_category_lists_valid_ones():
    r = search_products(category="gaita de fole")
    assert "category_not_found" in r and "Violões" in r["valid_categories"]


def test_find_by_name_and_ambiguity():
    one = get_product_details("Yamaha C40")
    assert one["product"]["name"].startswith("Yamaha C40")
    amb = get_product_details("Bateria Acústica Yamaha")
    assert amb["ambiguous"] and len(amb["matches"]) == 2


def test_unavailable_product_comes_with_alternatives():
    r = get_product_details("Giannini GF-3D Dreadnought Sunburst")
    assert r["product"]["availability"] == "out_of_stock"
    assert r["alternatives"] and all(a["availability"] == "available" for a in r["alternatives"])


def test_unknown_product():
    assert get_product_details("Stradivarius")["found"] is False


def test_limit_is_capped_and_sorted():
    r = search_products(category="ukulele", sort="price_desc", limit=100)
    prices = [float(p["price_to_pay"].replace("R$ ", "").replace(".", "").replace(",", ".")) for p in r["products"]]
    assert len(prices) <= 8 and prices == sorted(prices, reverse=True)


def test_category_aliases_resolve_to_the_right_category(cat):
    names = lambda text: cat.category_names(cat.resolve_categories(text))
    assert names("violão") == ["Violões"] and names("violões") == ["Violões"]
    assert names("guitarra") == ["Guitarras"]
    assert names("ukulele") == ["Ukuleles"]
    assert names("bateria") == ["Baterias e Percussão"]


def test_violao_search_returns_products():
    r = search_products(category="violão", query="iniciante nylon", max_price=800)
    assert r["count"] > 0 and all(p["category"] == "Violões" for p in r["products"])