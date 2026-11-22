"""Business rules used by the synthetic ShopFlow application."""

from decimal import Decimal

# Observing a status in old data does not make it a supported current state.
ORDER_STATES = frozenset(
    {"open", "confirmed", "fulfilled", "cancelled", "returned", "on_hold"}
)
INVOICE_STATES = frozenset({"draft", "open", "paid", "void"})
SHIPMENT_STATES = frozenset(
    {"planned", "in_transit", "delayed", "delivered", "returned"}
)
PAYMENT_ROLES = {
    ("authorization", "approved"): 0,
    ("capture", "settled"): 1,
    ("refund", "completed"): 0,
    ("failure", "declined"): 0,
}
# This small application's currency contract is explicit; unknown currencies fail.
CURRENCY_SCALE = {"USD": 2, "EUR": 2, "JPY": 0}


def money_from_minor(value, currency):
    """Billing stores money in minor units; operations stores major-unit decimals."""
    if type(value) is not int or currency not in CURRENCY_SCALE:
        raise ValueError("A known currency and integer minor amount are required")
    return Decimal(value).scaleb(-CURRENCY_SCALE[currency])


def uncaptured_amount(order, payments):
    """Order total not covered by settled captures, not a legal receivable.

    Authorization only reserves funds. A failed attempt contributes nothing.
    Refunds do not reopen collection debt; returned/cancelled orders are excluded.
    This policy differs from a billing invoice's outstanding amount.
    """
    if order["status"] not in ORDER_STATES:
        raise ValueError("Historical order state requires review")
    if order["status"] in {"cancelled", "returned"}:
        return Decimal(0)
    if order["currency"] not in CURRENCY_SCALE:
        raise ValueError("Unsupported currency")
    result = Decimal(str(order["totals"]["grandTotal"]))
    seen = set()
    for p in payments:
        if p["orderId"] != order["_id"]:
            raise ValueError("Payment belongs to a different order")
        if p["_id"] in seen or p["currency"] != order["currency"]:
            raise ValueError("Duplicate payment or incompatible currency")
        seen.add(p["_id"])
        role = (p["transactionType"], p["status"])
        if role not in PAYMENT_ROLES:
            raise ValueError("Unknown payment state")
        result -= Decimal(str(p["amount"])) * PAYMENT_ROLES[role]
    return max(result, Decimal(0))


def invoice_outstanding(invoice):
    """Open invoice balance is issued total less cash applied and credit notes.

    Credit notes reduce the legal invoice claim; unlike an order refund, they
    explicitly reduce this balance. The total may combine multiple orders.
    Draft and void invoices create no collectible balance in this application.
    """
    if invoice["status"] not in INVOICE_STATES:
        raise ValueError("Unsupported invoice status")
    if invoice["status"] in {"draft", "void"}:
        return Decimal(0)
    return money_from_minor(
        invoice["grossMinor"]
        - invoice["cashAppliedMinor"]
        - invoice["creditNotesMinor"],
        invoice["currency"],
    )


def credit_release_eligible(order, assessment):
    """Eligibility is a candidate capability, not permission to execute it.

    An active hold must be credit-related and the latest assessment must approve
    release. The service separately requires a finance approver and expected
    record version. A shipping delay does not qualify for a credit release.
    """
    return (
        order["status"] == "on_hold"
        and order.get("hold", {}).get("reason") == "credit_review"
        and assessment["subject"]["customerId"] == order["customerId"]
        and assessment["assessmentType"] == "credit_risk"
        and assessment["conclusion"] == "release_approved"
    )
