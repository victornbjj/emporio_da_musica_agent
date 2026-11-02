""" Assumprions (see docs/data_qualit.md): estimed_delivery stands in
 for the real delivey date, and every  order in the dataset is an online order. """

from dataclasses import dataclass, field
from datetime import date

REGRET_DAYS  = 7
DEFECT_EXCHANGE_DAYS = 30
LEGAL_WARRANTY_DAYS = 90


@dataclass
class ReturnCheck:
    order_id: int
    status: str
    delivered: bool
    days_since_purchase: int
    day_since_delivery: int | None
    regret_eligible: bool = False
    defect_exchange_eligible: bool = False
    legal_warranty_eligible: bool = False
    notes : list[str] = field(default_factory=list)




def check_return_eligibility(
    order_id: int,
    status: str,
    order_date: date,
    delivery_date: date | None,
    today: date,
) -> ReturnCheck:
    since_purchase = (today - order_date).days
    delivered = status == "delivered" and delivery_date is not None
    since_delivery = (today - delivery_date).days if delivered  else None
    check = ReturnCheck(order_id, status, delivered, since_purchase, since_delivery)


    if status == "cancelled":
        check.notes.append("Order was cancelled, nothing to return. ")
        return check

    if not delivered:
        check.notes.append(
            "Order not delivered yet: return and warranty periods start at receipt. "
        )
        return check

    check.regret_eligible = since_delivery <= REGRET_DAYS
    check.defect_exchange_eligible = since_purchase <= DEFECT_EXCHANGE_DAYS
    check.legal_warranty_eligible = since_delivery < LEGAL_WARRANTY_DAYS
    if not check.defect_exchange_eligible and check.legal_warranty_eligible:
        check.notes.append(
            "Store exchange window (30 days) is over, but te 90-day legal warranty still"
            "appilies; the manufacturer warranty can be triggered, and the store can help"
        )
    return check
