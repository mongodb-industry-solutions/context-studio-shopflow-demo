# Operations policy — version 1, effective 1 October 2026

A customer is a person or organization that places orders. `customerNumber` is
the stable business identifier used in integrations; `_id` is local to this system.
An organization has procurement details that do not apply to a person. A shipping
address is a component, not another customer.

An order expresses a purchase commitment. `orderType` selects a delivery, pickup,
gift, subscription or digital workflow. These alternatives carry different
requirements: pickup needs a store/window, a subscription has recurrence and
activation, and digital delivery issues a license. A gift additionally has a
recipient and price-hiding instructions. Optional notes and language keys do not
create new kinds of order.

The current order states are `open`, `confirmed`, `fulfilled`, `cancelled`,
`returned` and `on_hold`. Here `open` means the order has not yet been confirmed.
Some imported records retain `ready_legacy`. That historical value is not in the
current contract. A domain owner must decide whether it is rejected, translated
with evidence, or supported under a separately versioned contract.

Payments are occurrences: authorization reserves funds, capture settles funds,
failure records an unsuccessful attempt and refund records money sent back.
`amount` is expressed in major currency units. An order may have several capture
records; an authorization must never be counted again as a payment. An order can
have several parcel fulfillments; counting joined rows is not counting orders.

“Uncaptured order amount” is the original grand total minus settled captures.
Cancelled and returned orders are excluded. Refunds do not reopen collection debt
in this application. This measure is different from an invoice receivable.
Different currencies remain separate.

A risk assessment is a time-bounded statement about a customer, with author,
evidence, conclusion and sometimes model confidence. It is not an objective,
permanent customer attribute. A model's assessment is not a permission grant.
Credit release is eligible only for a credit-related order hold and a matching
assessment approving release. It still requires finance approval and an expected
order version. Executable code records this separation in `release_credit_hold`.
