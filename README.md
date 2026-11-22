# ShopFlow companion application

A deliberately synthetic commerce and billing application. All people, companies,
records and rules are fictional. This repository is a controlled demonstration,
not an independent benchmark of semantic inference.

Two systems answer different business questions:

- **Operations** owns customers, products, orders, payments, fulfillment, assessments and support cases.
- **Billing** owns billing accounts, invoices and account events. Its `customers` collection contains billing-account records, with local IDs independent of operations.

The business functions in `src/shopflow_demo/domain.py` and MongoDB access in
`store.py` are the executable implementation. The API description records their
inputs and outputs; it does not provision an HTTP server or expose credentials.

## Generate the data

```sh
PYTHONPATH=src python -m shopflow_demo.generate /tmp/shopflow-data
PYTHONPATH=src python -m unittest discover -s tests -v
```

The generator writes two folders of JSONL and a checksum manifest. It never
connects to a database. The consuming demonstration imports those files separately.
`store.py` accepts MongoDB database objects supplied by the caller.

Read `docs/operations.md`, `docs/billing.md` and `terminology/business.json` for
the application semantics. The historical memo in `docs/archive/` describes an
older policy and is retained to make version provenance explicit.

Tests are separate from repository-enrichment inputs. No generated semantic-map
answers or Context Studio implementation files belong to this repository.

## Calculation functions

`shopflow_demo.calculations` exposes two pure application functions with typed
signatures and documented evidence requirements:

- `order_collection_gap(order, payments)`: the order amount not covered by settled
  captures, preserving currency and distinguishing reservations from captures.
- `invoice_receivable(invoice)`: the invoice balance after cash and credit notes,
  converting the declared minor currency units to major units.

Both return JSON-compatible result objects and leave their inputs unchanged.
These functions illustrate code that a semantic inspection can discover as
candidate tools. They are not deployed HTTP endpoints. A consuming platform must
review the contract, bind complete authorized record inputs, verify the code
revision and register execution before exposing a callable capability.
