import pytest

from emporio_agent.data.loader import load_all
from emporio_agent.tools.checkout import calculate_shipping, payment_options
from emporio_agent.tools.orders import (
    NOT_VERIFIED,
    _payment_label,
    check_return,
    get_order_status,
)
from emporio_agent.tools.policies import search_policies
from emporio_agent.tools.registry import TOOL_SCHEMAS, dispatch


@pytest.fixture(scope="module")
def data():
    return load_all()


def owner_email(data, order_id):
    cid = data["orders"].loc[data["orders"].order_id == order_id, "customer_id"].iloc[0]
    return data["customers"].loc[data["customers"].customer_id == cid, "email"].iloc[0]


def test_correct_email_verifies(data):
    r = get_order_status(7, email=owner_email(data, 7))
    assert r["verified"] and r["order_id"] == 7 and r["items"]


def test_email_is_case_and_space_insensitive(data):
    assert get_order_status(7, email=f"  {owner_email(data, 7).upper()} ")["verified"]


def test_wrong_email_and_missing_order_look_identical(data):
    wrong = get_order_status(7, email="outra.pessoa@example.com")
    missing = get_order_status(99999, email=owner_email(data, 7))
    assert wrong == missing == NOT_VERIFIED


def test_no_proof_gives_no_data():
    assert get_order_status(7) == NOT_VERIFIED
    assert check_return(7) == NOT_VERIFIED


def test_another_customers_email_does_not_open_the_order(data):
    mine = owner_email(data, 7)
    other = next(e for e in data["customers"].email if e != mine)
    assert get_order_status(7, email=other) == NOT_VERIFIED


def test_late_shipped_order_is_flagged(data):
    r = get_order_status(8, email=owner_email(data, 8))      # shipped, estimate 2026-02-28
    assert r["status"] == "shipped" and r["delayed"] is True


def test_return_check_for_delivered_order(data):
    r = check_return(7, email=owner_email(data, 7))
    assert r["legal_warranty_eligible"] and not r["regret_eligible"]
    assert r["delivery_date_is_estimate"] is True


def test_cancelled_order_has_nothing_to_return(data):
    r = check_return(17, email=owner_email(data, 17))
    assert not r["legal_warranty_eligible"] and r["notes"]


def test_shipping_and_payment_tools():
    assert calculate_shipping("Campo Grande", 600)["fee"] == "R$ 0,00"
    assert calculate_shipping("Campo Grande", 100)["fee"] == "R$ 35,00"
    far = calculate_shipping("Dourados", 3000)
    assert far["fee"] is None and len(far["carrier_options"]) == 3
    p = payment_options(1200)
    assert p["max_installments"].startswith("12x") and not payment_options(2000)["can_combine_payment_methods"]


def test_large_item_note():
    r = calculate_shipping("Campo Grande", 4000, "Bateria Acústica Yamaha")
    assert any("special freight" in n.lower() for n in r["notes"])


def test_policy_tool():
    r = search_policies("quantos dias para devolver")
    assert r["found"] and r["sections"][0]["section"] == "4.1"
    assert search_policies("zzzz qwerty")["found"] is False


def test_dispatch_is_safe():
    assert "error" in dispatch("nao_existe", "{}")
    assert "error" in dispatch("payment_options", "{invalid json")
    assert "error" in dispatch("payment_options", '{"campo_inventado": 1}')
    assert dispatch("payment_options", '{"amount": 500}')["amount"] == "R$ 500,00"


def test_dispatch_validates_arguments_and_calls_tools():
    assert dispatch("search_products", '{"foo": 1}')["error"].startswith(
        "invalid arguments"
    )
    assert (
        dispatch(
            "get_order_status",
            '{"order_id": 12, "email": "patricia.cardoso@jmail.com"}',
        )["verified"]
        is True
    )
    assert dispatch("nao_existe", "{}")["error"].startswith("unknown tool")


def test_every_schema_has_a_function():
    from emporio_agent.tools.registry import _FUNCTIONS
    assert {t["function"]["name"] for t in TOOL_SCHEMAS} == set(_FUNCTIONS)

def test_cancelled_order_exposes_reason_after_verification(data):
    r = get_order_status(17, email=owner_email(data, 17))
    assert "cancelado pelo cliente" in r["notes"]
    assert get_order_status(17, email="outra.pessoa@example.com") == NOT_VERIFIED

def test_payment_method_is_human_readable(data):
    assert get_order_status(1, email=owner_email(data, 1))["payment_method"] == "PIX"
    assert get_order_status(2, email=owner_email(data, 2))["payment_method"] == "cartão de crédito em 6x"


def test_order_without_estimated_delivery_does_not_crash():
    r = get_order_status(12, email="patricia.cardoso@jmail.com")
    assert r["verified"] and r["estimated_delivery"] is None and r["delayed"] is False


def test_cancelled_order_exposes_reason():
    r = get_order_status(17, email="matheus.correia@hayoo.com.br")
    assert r["status"] == "cancelled" and "cancelado" in r["notes"]


def test_other_customers_email_is_rejected():
    assert get_order_status(5, email="anacarol.ferreira@coldmail.com")["verified"] is False


def test_debit_label():
    assert _payment_label("debit") == "cartão de débito"