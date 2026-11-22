"""MongoDB access used by the companion application; no inferred bindings."""

from .domain import uncaptured_amount, invoice_outstanding, credit_release_eligible


def unpaid_orders(operations, customer_number, *, actor_role):
    if actor_role not in {"finance_analyst", "finance_approver"}:
        raise PermissionError("Financial access required")
    customer = operations.customers.find_one({"customerNumber": customer_number})
    if not customer:
        return []
    result = []
    for order in operations.orders.find({"customerId": customer["_id"]}):
        amount = uncaptured_amount(
            order, operations.payments.find({"orderId": order["_id"]})
        )
        if amount > 0:
            result.append(
                {
                    "orderNumber": order["orderNumber"],
                    "amount": str(amount),
                    "currency": order["currency"],
                }
            )
    return result


def invoice_balances(operations, billing, customer_number, *, actor_role):
    if actor_role not in {"finance_analyst", "finance_approver"}:
        raise PermissionError("Financial access required")
    customer = operations.customers.find_one({"customerNumber": customer_number})
    if not customer:
        return []
    # Cross-system matching uses business identifiers, never coincident local _id.
    accounts = list(
        billing.customers.find(
            {
                "externalRefs.system": "shopflow",
                "externalRefs.customerNumber": customer_number,
            }
        )
    )
    return [
        {
            "invoiceNumber": row["invoiceNumber"],
            "amount": str(invoice_outstanding(row)),
            "currency": row["currency"],
        }
        for row in billing.invoices.find(
            {"customerId": {"$in": [a["_id"] for a in accounts]}}
        )
    ]


def release_credit_hold(
    operations, order_id, assessment, *, actor_role, expected_version
):
    """Named action: eligibility, authority and compare-and-set are separate."""
    if actor_role != "finance_approver":
        raise PermissionError("Finance approval required")
    order = operations.orders.find_one({"_id": order_id})
    if not order or not credit_release_eligible(order, assessment):
        raise ValueError("Credit release preconditions are not met")
    result = operations.orders.update_one(
        {
            "_id": order_id,
            "version": expected_version,
            "status": "on_hold",
            "hold.reason": "credit_review",
        },
        {"$set": {"status": "confirmed"}, "$inc": {"version": 1}},
    )
    if result.modified_count != 1:
        raise ValueError("Order changed; recheck before retrying")
    return {"orderId": order_id, "status": "confirmed", "version": expected_version + 1}
