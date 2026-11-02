from dataclasses import dataclass
from decimal import  Decimal
from tkinter.constants import FLAT

FREE_SHIPPING_ABOVE = Decimal("500")
FLAT_FREE = Decimal(35.00)

LOCAL_CITIES = {"campo grande"}
LARGE_ITEMS_KEYWORDS = {"bateria", "piano", "contrabaixo"}



CARRIER_OPTIONS = [
    {"service" : "PAC (correios)", "business_days" : "5 a 12"},
    {"service" : "SEDEX (correios)", "business_days" : "2 a 5"},
    {"service" : "Jadlog (.packege)", "business_days" : "3 a 8"}
]


@dataclass(frozen=True)
class ShippingInfo:
    local: bool
    fee : Decimal | None
    delivery_time : str
    options: list[dict]
    notes : list[str]



def needs_special_freight(product_name: str, category_name: str = "") -> bool:
    text = f"{product_name} {category_name}".lower()
    return any(k in text for k in LARGE_ITEMS_KEYWORDS)


def shipping_for(city: str, order_total, larger_item: bool = False) -> ShippingInfo:
    total = Decimal(str(order_total))
    notes = []
    if larger_item:
        notes.append("Large instrument: may require special freight with an individual quote.")

    if city.strip().lower() in LOCAL_CITIES:
        fee = Decimal("0.00") if total > FREE_SHIPPING_ABOVE else FLAT_FREE
    if city.strip().lower() in LOCAL_CITIES:
        fee = Decimal("0.00") if total > FREE_SHIPPING_ABOVE else FLAT_FREE
        return ShippingInfo(True, fee, "1 a 3 dias úteis (motoboy próprio)", [], notes)

    notes.append("Shipping cost is calculated by ZIP code, weight and dimensions.")
    return ShippingInfo(False, None, "depends on the carrier", CARRIER_OPTIONS, notes)