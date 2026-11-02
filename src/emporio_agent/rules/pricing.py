from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

import pandas as pd

PIX_DISCOUNT = Decimal("0.05")
COMBINED_PAYMENT_MIN = Decimal("2000")


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def format_brl(value) -> str:
    """ Format a number the Brazilian way: 1234.5  -> 'R$ 1234.50' """
    text = f"{money(value):,.2f}"
    return "R$ " + text.replace("," , "_").replace(".", ",").replace("_", ".")


def active_promotion_percent(promotions: pd.DataFrame, product_id: int) -> int | None:
    """Return the discount % of the active promotion, or None. Inactive rows are ignored."""
    rows = promotions[(promotions.product_id == product_id) & (promotions.is_active)]
    if rows.empty:
        return None
    return int(rows.discount_percent.max())  # defensive: highest if several are active




@dataclass(frozen=True)
class PriceQuote:
    original : Decimal
    promo_percent: int | None
    final_price: Decimal
    pix_price : Decimal | None
    pix_applies : bool



def quote_price(price_brl, promo_percent : int | None = None) -> PriceQuote:
    original = money(price_brl)
    if promo_percent is not None:
        final = money(original * (Decimal(1) - Decimal(promo_percent) / Decimal(100)))
        return PriceQuote(original, promo_percent, final, None, False)

    return PriceQuote(original, None, original, money(original * (1 - PIX_DISCOUNT)), True)



def allowed_installments(amount) -> list[tuple[int, Decimal]]:

    total = money(amount)
    options = []

    for n in range(1,13):
        per = total / n
        minimum = 0 if n == 1 else 50 if n <= 3 else 80 if n <= 6 else 100

        if per >= minimum:
            options.append((n, money(per)))

    return options


def can_combine_payment_methods(amount) -> bool:

    return money(amount) > COMBINED_PAYMENT_MIN

