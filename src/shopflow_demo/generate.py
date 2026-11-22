"""Deterministic synthetic operations + billing databases. No customer data.

Run as python -m shopflow_demo.generate OUTPUT_DIRECTORY. Writes JSONL and a
manifest only; importing into MongoDB is an explicit separate operation.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import argparse
import json
from pathlib import Path

VERSION = "shopflow_vision.v1"
BASE = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)


def at(day):
    return (BASE + timedelta(days=day)).isoformat()


def build():
    ops = {
        name: []
        for name in (
            "customers",
            "products",
            "orders",
            "payments",
            "fulfillments",
            "assessments",
            "support_cases",
        )
    }
    billing = {name: [] for name in ("customers", "invoices", "account_events")}
    for i in range(1, 25):
        business = i % 3 == 0
        c = {
            "_id": f"cust-{i:03}",
            "customerNumber": f"CUST-{i:04}",
            "partyType": "organization" if business else "person",
            "displayName": f"ShopFlow Business {i}"
            if business
            else f"Demo Customer {i}",
            "status": "active",
            "locale": ["en", "es", "fr"][i % 3],
            "segment": ["standard", "loyal", "strategic"][i % 3],
            "createdAt": at(-60 + i),
            "contact": {"email": f"customer{i}@example.test"},
            "addresses": [{"kind": "shipping", "city": "Barcelona", "country": "ES"}],
        }
        if business:
            c["organization"] = {
                "legalName": f"ShopFlow Business {i} Ltd",
                "registrationCode": f"DEMO-REG-{i}",
                "buyer": {"name": f"Buyer {i}", "purchaseOrderRequired": True},
            }
        else:
            c["person"] = {
                "givenName": "Demo",
                "familyName": f"Customer {i}",
                "loyalty": {"points": i * 10},
            }
        ops["customers"].append(c)
        # Rotated local IDs intentionally collide with another operations customer.
        account = {
            "_id": f"cust-{i % 24 + 1:03}",
            "accountNumber": f"ACC-{i:04}",
            "legalName": c["displayName"],
            "status": "open",
            "externalRefs": {
                "system": "shopflow",
                "customerNumber": c["customerNumber"],
            },
            "creditLimitMinor": 500000 if business else 50000,
            "currency": "EUR",
            "paymentTerms": "NET30" if business else "PREPAID",
            "contact": {"email": f"accounts{i}@example.test"},
            "recordedAt": at(-10),
        }
        if i == 1:
            account["legalName"] = "Demo Customer One"  # Source disagreement retained.
            account["legacySegment"] = "gold"
        billing["customers"].append(account)
    for i in range(1, 13):
        kind = ["physical", "digital", "subscription"][i % 3]
        p = {
            "_id": f"product-{i:03}",
            "sku": f"SKU-{i:03}",
            "productKind": kind,
            "name": {"en": f"Demo product {i}", "es": f"Producto de demostración {i}"},
            "unitPrice": 25 + i,
            "currency": "EUR",
        }
        if kind == "physical":
            p["shipping"] = {
                "weight": {"value": 0.5 + i / 10, "unit": "kg"},
                "fragile": i % 2 == 0,
            }
        elif kind == "digital":
            p["license"] = {"termDays": 365, "maxDevices": 3}
        else:
            p["recurrence"] = {"interval": "month", "trialDays": 14}
        ops["products"].append(p)
    kinds = ["delivery", "pickup", "gift", "subscription", "digital"]
    states = ["confirmed", "fulfilled", "open", "on_hold", "returned", "cancelled"]
    for i in range(1, 121):
        ci = (i - 1) % 24 + 1
        kind = kinds[(i - 1) % 5]
        status = states[(i - 1) % 6]
        amount = Decimal(100 + (i % 5) * 25)
        o = {
            "_id": f"ord-{i:04}",
            "orderNumber": f"ORD-{1000 + i}",
            "customerId": f"cust-{ci:03}",
            "orderType": kind,
            "status": status,
            "currency": "EUR",
            "createdAt": at(i % 24),
            "version": 1,
            "totals": {"grandTotal": float(amount), "taxIncluded": True},
            "lines": [
                {
                    "productId": f"product-{(i - 1) % 12 + 1:03}",
                    "quantity": 1,
                    "unitPrice": float(amount),
                }
            ],
        }
        if kind in {"delivery", "gift"}:
            o["delivery"] = {
                "address": {"city": "Barcelona", "country": "ES"},
                "promisedAt": at(i % 24 + 3),
            }
            if kind == "gift":
                o["gift"] = {
                    "recipient": {"name": "Demo recipient"},
                    "hidePrices": True,
                    "message": "Happy birthday",
                }
        elif kind == "pickup":
            o["pickup"] = {
                "storeId": "store-01",
                "window": {"from": at(i % 24 + 1), "to": at(i % 24 + 2)},
            }
        elif kind == "subscription":
            o["subscription"] = {
                "interval": "month",
                "activationState": "pending" if status == "on_hold" else "active",
                "nextRenewalAt": at(i % 24 + 30),
            }
        else:
            o["digital"] = {
                "recipientEmail": f"user{ci}@example.test",
                "licenseState": "issued",
            }
        if status == "on_hold":
            o["hold"] = {"reason": "credit_review", "since": at(i % 24)}
        if i == 1:
            o.update(status="on_hold", hold={"reason": "credit_review", "since": at(1)})
        if i == 2:
            o["status"] = "ready_legacy"  # Observed does not mean authoritative.
        if i == 6:
            o["currency"] = "USD"
        if i == 7:
            o["currency"] = "JPY"
            o["totals"]["grandTotal"] = 10000
        amount = Decimal(str(o["totals"]["grandTotal"]))
        ops["orders"].append(o)
        events = [("authorization", "approved", amount)]
        if i == 1:
            events += [("capture", "settled", Decimal("50"))]  # EUR 75 remains.
        elif i % 10 == 0:
            events += [
                ("capture", "settled", amount / 2),
                ("capture", "settled", amount / 2),
            ]
        elif i % 7 == 0:
            events += [("failure", "declined", amount)]
        else:
            events += [("capture", "settled", amount)]
        if o["status"] == "returned":
            events += [("refund", "completed", amount)]
        for j, (tx, state, value) in enumerate(events):
            e = {
                "_id": f"pay-{i:04}-{j}",
                "orderId": o["_id"],
                "customerId": o["customerId"],
                "transactionType": tx,
                "status": state,
                "amount": float(value),
                "currency": o["currency"],
                "occurredAt": at(i % 24 + j),
            }
            if tx == "failure":
                e["failure"] = {"code": "insufficient_funds", "retryable": True}
            elif tx == "refund":
                e["refund"] = {
                    "reason": "returned_item",
                    "originalCaptureId": f"pay-{i:04}-1",
                }
            else:
                e["processor"] = {"reference": f"DEMO-{i}-{j}", "channel": "card"}
            ops["payments"].append(e)
        # Multiple parcels prove one-to-many relationships and partial fulfillment.
        for part in range(2 if i % 5 == 0 else 1):
            fk = "parcel" if kind in {"delivery", "gift"} else kind
            f = {
                "_id": f"ful-{i:04}-{part}",
                "orderId": o["_id"],
                "fulfillmentType": fk,
                "status": "delayed" if i % 9 == 0 else "delivered",
                "occurredAt": at(i % 24 + 3),
            }
            if fk == "parcel":
                f["parcel"] = {
                    "trackingNumber": f"TRACK-{i}-{part}",
                    "carrier": "Demo Carrier",
                    "weight": {"value": 1.2, "unit": "kg"},
                }
            elif fk == "pickup":
                f["pickup"] = {"storeId": "store-01", "collectedBy": "Demo recipient"}
            elif fk == "digital":
                f["license"] = {
                    "keyRef": f"lic-{i}",
                    "deliveryEmail": f"user{ci}@example.test",
                }
            else:
                f["activation"] = {
                    "subscriptionOrderId": o["_id"],
                    "effectiveAt": at(i % 24),
                }
            ops["fulfillments"].append(f)
        account_id = f"cust-{ci % 24 + 1:03}"
        scale = 0 if o["currency"] == "JPY" else 2
        gross = int(amount.scaleb(scale))
        applied = 2000 if i == 1 else (gross if i % 7 else 0)
        inv = {
            "_id": f"inv-{i:04}",
            "invoiceNumber": f"INV-{2000 + i}",
            "customerId": account_id,
            "status": "open" if applied < gross else "paid",
            "currency": o["currency"],
            "grossMinor": gross,
            "cashAppliedMinor": applied,
            "creditNotesMinor": 1000 if i == 1 else 0,
            "orderRefs": [{"system": "shopflow", "orderNumber": o["orderNumber"]}],
            "issuedAt": at(i % 24),
            "dueAt": at(i % 24 + 30),
        }
        billing["invoices"].append(inv)
    # Assessments are statements by an actor/model with time and evidence, not entities.
    for i in range(1, 25):
        ops["assessments"].append(
            {
                "_id": f"assessment-{i:03}",
                "assessmentType": "credit_risk" if i % 2 else "delivery_risk",
                "subject": {"customerId": f"cust-{i:03}"},
                "conclusion": "release_approved" if i == 1 else "review_required",
                "assessedAt": at(25),
                "validUntil": at(30),
                "provenance": {
                    "kind": "human" if i % 3 else "model",
                    "actor": f"demo-reviewer-{i % 3}",
                    "modelVersion": "demo-v1" if i % 3 == 0 else None,
                },
                "evidenceRefs": [{"collection": "orders", "id": f"ord-{i:04}"}],
                "confidence": 0.8 if i % 3 == 0 else None,
            }
        )
        billing["account_events"].append(
            {
                "_id": f"acc-event-{i:03}",
                "customerId": f"cust-{i % 24 + 1:03}",
                "eventType": "credit_limit_changed",
                "previousMinor": 25000,
                "currentMinor": 50000,
                "currency": "EUR",
                "occurredAt": at(24),
                "actor": "demo-finance",
            }
        )
        ops["support_cases"].append(
            {
                "_id": f"case-{i:03}",
                "caseType": "billing_question" if i % 2 else "delivery_issue",
                "customerId": f"cust-{i:03}",
                "orderId": f"ord-{i:04}",
                "status": "open",
                "openedAt": at(26),
                "request": {
                    "text": "Please explain my balance"
                    if i % 2
                    else "Where is my delivery?",
                    "language": "en",
                },
                "messages": [
                    {"authorRole": "customer", "text": "Can you help?", "at": at(26)}
                ],
            }
        )
    return {"operations": ops, "billing": billing}


def write(output):
    output.mkdir(parents=True, exist_ok=True)
    result = {"version": VERSION, "synthetic": True, "databases": {}}
    for database, collections in build().items():
        directory = output / database
        directory.mkdir(exist_ok=True)
        result["databases"][database] = {}
        for collection, rows in collections.items():
            raw = "".join(
                json.dumps(r, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
                + "\n"
                for r in sorted(rows, key=lambda r: r["_id"])
            ).encode()
            (directory / (collection + ".jsonl")).write_bytes(raw)
            result["databases"][database][collection] = {
                "records": len(rows),
                "sha256": sha256(raw).hexdigest(),
                "bytes": len(raw),
            }
    (output / "manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("output", type=Path)
    args = p.parse_args()
    print(json.dumps(write(args.output), indent=2))
