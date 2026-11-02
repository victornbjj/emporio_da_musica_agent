from datetime import date
from decimal import Decimal

import pandas as pd

from emporio_agent.rules.pricing import (
    active_promotion_percent, allowed_installments, can_combine_payment_methods, quote_price,
)
from emporio_agent.rules.returns import check_return_eligibility
from emporio_agent.rules.shipping import needs_special_freight, shipping_for


def test_inactive_promotions_are_ignored():
    promos = pd.DataFrame(
        {"product_id": [1, 1, 2], "discount_percent": [40, 10, 15], "is_active": [False, True, False]}
    )
    assert active_promotion_percent(promos, 1) == 10
    assert active_promotion_percent(promos, 2) is None


def test_pix_applies_without_promo():
    q = quote_price(1000)
    assert q.pix_applies and q.pix_price == Decimal("950.00")


def test_pix_does_not_stack_with_promo():
    q = quote_price(1000, 20)
    assert q.final_price == Decimal("800.00")
    assert q.pix_price is None and not q.pix_applies


def test_installments_respect_minimums():
    opts = dict(allowed_installments(240))      # 3x=80 ok, 4x=60 (<80) no
    assert 3 in opts and 4 not in opts
    assert max(dict(allowed_installments(1200))) == 12
    assert max(dict(allowed_installments(150))) == 3   # 3x=50 ok, 4x=37.5 no


def test_small_amount_only_single_payment():
    assert [n for n, _ in allowed_installments(90)] == [1]   # 2x=45 (<50)


def test_combined_payment_threshold():
    assert not can_combine_payment_methods(2000)
    assert can_combine_payment_methods(2000.01)


def test_return_windows():
    # delivered 2026-02-17, today 2026-03-31 -> 42 days since delivery
    c = check_return_eligibility(7, "delivered", date(2026, 2, 3), date(2026, 2, 17), date(2026, 3, 31))
    assert not c.regret_eligible and not c.defect_exchange_eligible and c.legal_warranty_eligible


def test_regret_window_is_inclusive_at_7_days():
    c = check_return_eligibility(1, "delivered", date(2026, 3, 1), date(2026, 3, 10), date(2026, 3, 17))
    assert c.regret_eligible
    c = check_return_eligibility(1, "delivered", date(2026, 3, 1), date(2026, 3, 10), date(2026, 3, 18))
    assert not c.regret_eligible


def test_undelivered_and_cancelled_orders():
    c = check_return_eligibility(8, "shipped", date(2026, 2, 15), None, date(2026, 3, 31))
    assert not c.delivered and not c.regret_eligible
    c = check_return_eligibility(17, "cancelled", date(2026, 1, 28), None, date(2026, 3, 31))
    assert not c.legal_warranty_eligible


def test_local_shipping_threshold():
    assert shipping_for("Campo Grande", 500).fee == Decimal("35.00")      # "acima de" 500
    assert shipping_for("Campo Grande", 500.01).fee == Decimal("0.00")
    assert shipping_for(" campo grande ", 100).local


def test_other_city_needs_quote():
    s = shipping_for("Dourados", 3000)
    assert not s.local and s.fee is None and len(s.options) == 3


def test_special_freight_detection():
    assert needs_special_freight("Bateria Acústica Pearl")
    assert not needs_special_freight("Violão Tagima")