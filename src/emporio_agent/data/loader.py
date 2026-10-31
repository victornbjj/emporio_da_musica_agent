"""Load and clean the raw CSVs, and audit them for inconsistencies."""

import json

import pandas as pd

from .. config import RAW_DATA_DIR



def _read(name: str) -> pd.DataFrame:
    return  pd.read_csv(RAW_DATA_DIR / f"{name}.csv")



def load_all() -> dict[str, pd.DataFrame]:

    products = _read("products")
    products["specs"] = products["specs"].apply(
        lambda s: json.loads(s) if isinstance(s, str) and s.strip() else{}
    )

    products["created_at"] = pd.to_datetime(products["created_at"])


    promotions = _read("promotions")
    promotions["is_active"] = promotions["is_active"].astype(bool)


    customers = _read("customers")
    customers["email"] = customers["email"].str.strip().str.lower()


    orders = _read("orders")
    for col in ("order_date", "estimated_delivery"):
       orders[col] = pd.to_datetime(orders[col])

    return {
        "products" : products,
        "categories" : _read("categories"),
        "promotions" : promotions,
        "customers" : customers,
        "orders" : orders,
        "order_items": _read("order_items")


   }






def audit(d: dict[str, pd.DataFrame]) -> list[str]:
    """Return human-readable data-quality findings."""
    p, c, pr = d["products"], d["categories"], d["promotions"]
    cu, o, oi = d["customers"], d["orders"], d["order_items"]
    issues: list[str] = []

    # Products: status vs stock
    for _, r in p[(p.status == "active") & (p.stock_quantity == 0)].iterrows():
        issues.append(f"Product {r.product_id} '{r['name']}' is active but has stock 0")
    for _, r in p[(p.status != "active") & (p.stock_quantity > 0)].iterrows():
        issues.append(
            f"Product {r.product_id} '{r['name']}' is {r.status} but has stock {r.stock_quantity}"
        )

    # Categories without products
    empty = c[~c.category_id.isin(p.category_id)]
    for _, r in empty.iterrows():
        issues.append(f"Category {r.category_id} '{r['name']}' has no products")

    # Promotions
    active = pr[pr.is_active]
    issues.append(f"Only {len(active)} of {len(pr)} promotions are active")
    multi = pr.groupby("product_id").size()
    for pid in multi[multi > 1].index:
        issues.append(f"Product {pid} has {multi[pid]} promotion rows (check which is active)")
    for _, r in active.merge(p, on="product_id").query("status != 'active'").iterrows():
        issues.append(f"Active promotion on non-active product {r.product_id}")
    for pid in pr[~pr.product_id.isin(p.product_id)].product_id.unique():
        issues.append(f"Promotion references unknown product {pid}")

    # Customers
    for email in cu[cu.email.duplicated(keep=False)].email.unique():
        ids = cu[cu.email == email].customer_id.tolist()
        issues.append(f"Duplicate email {email} for customers {ids}")

    # Orders
    for pid in oi[~oi.product_id.isin(p.product_id)].product_id.unique():
        issues.append(f"order_items references unknown product {pid}")
    bad = oi.merge(p, on="product_id").query("status != 'active'")
    for _, r in bad.iterrows():
        issues.append(f"Order {r.order_id} contains {r.status} product {r.product_id}")

    totals = oi.merge(p[["product_id", "price_brl"]], on="product_id")
    totals["line"] = totals.quantity * totals.price_brl
    calc = totals.groupby("order_id").line.sum()
    for _, r in o.iterrows():
        diff = round(r.total_brl - calc.get(r.order_id, 0), 2)
        if diff != 0:
            issues.append(
                f"Order {r.order_id}: total {r.total_brl} != sum of items "
                f"{calc.get(r.order_id, 0)} (diff {diff})"
            )

    delivered = o[o.status == "delivered"]
    issues.append(
        f"No delivered_at column: using estimated_delivery as proxy for {len(delivered)} delivered orders"
    )
    return issues



if __name__ == "__main__":
    for i in audit(load_all()):
        print("-" ,i)