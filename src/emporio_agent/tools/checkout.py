"""Shipping and payment tools. Math lives in rules/, these are thin wrappers."""
from ..data.repository import get_catalog
from ..rules.pricing import allowed_installments, can_combine_payment_methods, format_brl
from ..rules.shipping import needs_special_freight, shipping_for


def calculate_shipping(city: str, order_total: float, product_name: str | None = None) -> dict:
    large = False
    if product_name:
        large = any(
            needs_special_freight(r["name"], r["category"])
            for r in get_catalog().find_by_name(product_name)
        )
    s = shipping_for(city, order_total, large)
    return {
        "local_delivery": s.local,
        "fee": format_brl(s.fee) if s.fee is not None else None,   # None = quote by ZIP code
        "delivery_time": s.delivery_time,
        "carrier_options": s.options,
        "notes": s.notes,
    }


def payment_options(amount: float) -> dict:
    options = allowed_installments(amount)
    n, per = options[-1]
    return {
        "amount": format_brl(amount),
        "max_installments": f"{n}x de {format_brl(per)} sem juros",
        "all_installments": [f"{k}x de {format_brl(v)}" for k, v in options],
        "can_combine_payment_methods": can_combine_payment_methods(amount),
    }