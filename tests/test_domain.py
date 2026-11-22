import unittest
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock
from shopflow_demo.generate import build
from shopflow_demo.domain import (
    uncaptured_amount,
    invoice_outstanding,
    money_from_minor,
    credit_release_eligible,
)


class DomainTests(unittest.TestCase):
    def setUp(self):
        d = build()
        self.ops = d["operations"]
        self.billing = d["billing"]

    def test_measures_differ(self):
        order = self.ops["orders"][0]
        payments = [p for p in self.ops["payments"] if p["orderId"] == order["_id"]]
        self.assertEqual(uncaptured_amount(order, payments), Decimal("75"))
        self.assertEqual(
            invoice_outstanding(self.billing["invoices"][0]), Decimal("95")
        )

    def test_no_cross_system_id_join(self):
        a = self.ops["customers"][0]
        wrong = next(c for c in self.billing["customers"] if c["_id"] == a["_id"])
        self.assertNotEqual(
            wrong["externalRefs"]["customerNumber"], a["customerNumber"]
        )
        correct = next(
            c
            for c in self.billing["customers"]
            if c["externalRefs"]["customerNumber"] == a["customerNumber"]
        )
        self.assertEqual(correct["accountNumber"], "ACC-0001")

    def test_units_and_legacy(self):
        self.assertEqual(money_from_minor(12500, "EUR"), Decimal("125"))
        self.assertEqual(money_from_minor(10000, "JPY"), Decimal("10000"))
        with self.assertRaises(ValueError):
            money_from_minor(100, "ABC")
        with self.assertRaises(ValueError):
            uncaptured_amount(self.ops["orders"][1], [])

    def test_eligibility_is_specific(self):
        at = datetime(2026, 10, 27, tzinfo=timezone.utc)
        self.assertTrue(
            credit_release_eligible(
                self.ops["orders"][0], self.ops["assessments"][0], at=at
            )
        )
        self.assertFalse(
            credit_release_eligible(
                self.ops["orders"][0], self.ops["assessments"][1], at=at
            )
        )

    def test_expired_or_future_assessment_cannot_release(self):
        for at in [
            datetime(2026, 10, 1, tzinfo=timezone.utc),
            datetime(2026, 11, 22, tzinfo=timezone.utc),
        ]:
            self.assertFalse(
                credit_release_eligible(
                    self.ops["orders"][0], self.ops["assessments"][0], at=at
                )
            )
        with self.assertRaises(ValueError):
            credit_release_eligible(
                self.ops["orders"][0],
                self.ops["assessments"][0],
                at=datetime(2026, 10, 27),
            )

    def test_denied_reads_do_not_touch_database(self):
        from shopflow_demo.store import unpaid_orders, invoice_balances

        with self.assertRaises(PermissionError):
            unpaid_orders(None, "CUST-0001", actor_role="support")
        with self.assertRaises(PermissionError):
            invoice_balances(None, None, "CUST-0001", actor_role="support")

    def test_action_uses_stored_latest_assessment_and_compare_and_set(self):
        from shopflow_demo.store import release_credit_hold

        orders, assessments = Mock(), Mock()
        operations = SimpleNamespace(orders=orders, assessments=assessments)
        order, assessment = self.ops["orders"][0], self.ops["assessments"][0]
        orders.find_one.return_value = order
        assessments.find_one.return_value = assessment
        at = datetime(2026, 10, 27, tzinfo=timezone.utc)
        with self.assertRaises(PermissionError):
            release_credit_hold(
                None,
                order["_id"],
                assessment["_id"],
                actor_role="support",
                expected_version=1,
                at=at,
            )
        with self.assertRaises(ValueError):
            release_credit_hold(
                operations,
                order["_id"],
                "older-approval",
                actor_role="finance_approver",
                expected_version=1,
                at=at,
            )
        orders.update_one.assert_not_called()
        orders.update_one.return_value.modified_count = 0
        with self.assertRaisesRegex(ValueError, "Order changed"):
            release_credit_hold(
                operations,
                order["_id"],
                assessment["_id"],
                actor_role="finance_approver",
                expected_version=1,
                at=at,
            )
        self.assertEqual(orders.update_one.call_args.args[0]["version"], 1)
        orders.update_one.return_value.modified_count = 1
        result = release_credit_hold(
            operations,
            order["_id"],
            assessment["_id"],
            actor_role="finance_approver",
            expected_version=1,
            at=at,
        )
        self.assertEqual(result["version"], 2)

    def test_relationships_and_determinism(self):
        self.assertEqual(build(), build())
        for data in [self.ops, self.billing]:
            for rows in data.values():
                self.assertEqual(len(rows), len({r["_id"] for r in rows}))
        customers = {r["_id"] for r in self.ops["customers"]}
        orders = {r["_id"] for r in self.ops["orders"]}
        for name in ["orders", "payments", "support_cases"]:
            self.assertTrue(all(r["customerId"] in customers for r in self.ops[name]))
        for name in ["payments", "fulfillments", "support_cases"]:
            self.assertTrue(all(r["orderId"] in orders for r in self.ops[name]))
        accounts = {r["_id"] for r in self.billing["customers"]}
        self.assertTrue(
            all(r["customerId"] in accounts for r in self.billing["invoices"])
        )

    def test_polymorphism_and_partial_fulfillment(self):
        self.assertEqual(len({r["orderType"] for r in self.ops["orders"]}), 5)
        self.assertEqual(len({r["transactionType"] for r in self.ops["payments"]}), 4)
        self.assertGreater(len(self.ops["fulfillments"]), len(self.ops["orders"]))


if __name__ == "__main__":
    unittest.main()
