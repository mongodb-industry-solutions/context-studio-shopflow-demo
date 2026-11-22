"""Read-only calculation functions offered by the ShopFlow application.

Inputs are application records, not database credentials or executable queries.
The caller retrieves complete, authorized evidence before invoking a function.
These pure functions do not approve an action or change operational records.
"""
from decimal import Decimal

from .domain import uncaptured_amount, invoice_outstanding


def order_collection_gap(order: dict, payments: list[dict]) -> dict:
    """Calculate an order's amount not covered by settled payment captures.

    `order` is one operations.orders record. `payments` contains ALL related
    operations.payments records, joined by payments.orderId = order._id.
    Authorization reservations, refunds and failed attempts do not reduce this
    measure. Cancelled/returned orders have no collection gap. Historical states,
    duplicate payments, foreign-order payments and mixed currencies are rejected.
    The result uses major currency units and is not an invoice receivable.
    The caller must establish evidence completeness; this function cannot detect
    an omitted capture merely from the records it receives.
    """
    if not isinstance(order, dict) or not isinstance(payments, list):
        raise ValueError("An order and its complete payment list are required")
    values = [order['totals']['grandTotal'], *[p['amount'] for p in payments]]
    if any(isinstance(v, bool) or not Decimal(str(v)).is_finite() for v in values):
        raise ValueError("Money values must be finite numbers")
    return {'orderNumber': order['orderNumber'], 'amount': str(uncaptured_amount(order, payments)),
            'currency': order['currency'], 'unit': 'major', 'calculation': 'order_collection_gap'}


def invoice_receivable(invoice: dict) -> dict:
    """Calculate a billing invoice's balance after applied cash and credit notes.

    Input is one billing.invoices record: grossMinor, cashAppliedMinor and
    creditNotesMinor are integer minor currency units. The known currency scale
    converts the result to major units (EUR/USD: 100 minor units, JPY: 1).
    Draft/void invoices produce zero; unknown states/currencies are rejected.
    This is a receivable on an issued invoice, not a payment-authorization gap.
    """
    if not isinstance(invoice, dict) or any(type(invoice.get(k)) is not int
        for k in ('grossMinor', 'cashAppliedMinor', 'creditNotesMinor')):
        raise ValueError("Integer minor-unit invoice amounts are required")
    return {'invoiceNumber': invoice['invoiceNumber'], 'amount': str(invoice_outstanding(invoice)),
            'currency': invoice['currency'], 'unit': 'major', 'calculation': 'invoice_receivable'}
