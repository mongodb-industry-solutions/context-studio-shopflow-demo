# Billing policy — version 1, effective 1 October 2026

A billing account is the legal settlement relationship with a customer. The
collection is named `customers`, but it does not have the same identity or grain
as the operations customer. Join systems using
`externalRefs.system = shopflow` and `externalRefs.customerNumber`, never equal
local `_id` values. Billing `legalName` can differ from the operations display name.
Neither name wins automatically; each has its own purpose.

`status = open` on an invoice means it has an unpaid balance. `status = open` on
an account means the account is usable. Neither means an unconfirmed order. The
three value sets must remain separately qualified.

`grossMinor`, `cashAppliedMinor`, `creditNotesMinor` and `creditLimitMinor` are
integer minor-currency units. EUR and USD have two decimal places; JPY has none
in this application. Currency conversion is not supported.

Invoice receivable = issued gross amount − cash applied − credit notes. Draft
and void invoices create no collectible balance. A credit note can reduce an
invoice without changing captured order payments. Settlement posting can lag
payment capture. Consequently invoice receivable and uncaptured order amount
must not be merged into an unqualified “outstanding” measure.

`orderRefs` records operations order numbers with a system qualifier. It is a
relationship, not a copy of the complete order. Credit-limit changes are account
events. The credit limit is sensitive financial information: support users may
request delivery context, but financial balances and credit-limit changes belong
to finance roles.
