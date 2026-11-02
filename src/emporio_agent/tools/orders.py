"""Order tools. Every order lookup requires identity verification."""
import  os
import re
from dataclasses import  asdict
from datetime import date
from functools import  lru_cache



import pandas as pd


from ..data.loader import load_all
from ..data.repository import get_catalog
from ..rules.pricing import format_brl
from ..rules.returns import check_return_eligibility


# Same answer for "order does not exist" and "data does not match" (no order enumeration).

NOT_VERIFIED = {
    "verified" : False,
    "message": "Não encontrei um pedido com esses dados. Peça ao cliente para conferir "
               "o número do pedido e o e-mail (ou os 4 últimos dígitos do telefone)."
}

IN_TRANSIT = {"pending", "confirmed", "shipped"}
PAYMENTS_LABELS ={
    "pix" : "PIX",
    "boleto" : "boleto",
    "debito": "cartão de débito"
}


def _payment_label(code):
    code = str(code)
    if code.startswith("credit"):
        return f"cartão de crédito em {code.removeprefix('credit_')}"
    return PAYMENTS_LABELS.get(code, code)


def today() -> date:
  return date.fromisoformat(os.getenv("AS_OF_DATE", "2026-03-31"))



@lru_cache(maxsize=1)
def _data() -> dict:
    return load_all()


def _digits(value) -> str:
    return re.sub(r"\D", "", str(value))



def _verify(order_id, email, phone_last4):
    """Return (order, customer) only if the proof matches the order's OWN customer."""
    d = _data()
    try:
        oid = int(order_id)
    except (TypeError, ValueError):
        return  None

    rows = d["orders"][d["orders"].order_id == oid]

    if rows.empty:
        return None
    order = rows.iloc[0]

    cust = d["customers"][d["customers"].customer_id == order.customer_id].iloc[0]


    ok = False
    if email:
        ok = str(email).strip().lower() == cust.email
    if not ok and phone_last4:
        last4 = _digits(phone_last4)
        ok = len(last4) == 4 and _digits(cust.phone).endswith(last4)
    return (order, cust) if ok else None


def get_order_status(order_id: int, email: str | None = None,
                     phone_last4: str | None = None) -> dict:
    verifield = _verify(order_id, email, phone_last4)
    if verifield is None:
        return NOT_VERIFIED
    order , _ = verifield

    d = _data()
    names = names = {r["product_id"]: r["name"] for r in get_catalog().rows}
    items = d["order_items"][d["order_items"].order_id == order.order_id]
    lines = [
        {"product": names.get(int(i.product_id), f"produto {int(i.product_id)}"),
         "quantity": int(i.quantity)}
        for i in items.itertuples()
    ]

    estimated = order.estimated_delivery.date()
    out = {
        "verified": True,
        "order_id": int(order.order_id),
        "status": order.status,
        "order_date": str(order.order_date.date()),
        "estimated_delivery": str(estimated),
        "total_paid": format_brl(order.total_brl),
        "payment_method": _payment_label(order.payment_method),
        "items": lines,
        "delayed": order.status in IN_TRANSIT and estimated < today(),
    }
    if pd.notna(order.notes):
        out["notes"] = str(order.notes)
    if pd.notna(order.tracking_code):
        out["tracking_code"] = str(order.tracking_code)
    return out


def check_return(order_id: int, email: str | None = None,
                 phone_last4: str | None = None) -> dict:
    verified = _verify(order_id, email, phone_last4)
    if verified is None:
        return NOT_VERIFIED
    order, _ = verified

    # Assumption A2: estimated_delivery stands in for the real delivery date.
    delivery = order.estimated_delivery.date() if order.status == "delivered" else None
    check = check_return_eligibility(
        int(order.order_id), order.status, order.order_date.date(), delivery, today()
    )
    return {"verified": True, "delivery_date_is_estimate": True, **asdict(check)}