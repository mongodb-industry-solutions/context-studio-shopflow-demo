import unittest
from copy import deepcopy
from shopflow_demo.calculations import order_collection_gap, invoice_receivable
from shopflow_demo.generate import build


class CalculationToolsTests(unittest.TestCase):
    def setUp(self):
        data = build()
        self.order = data['operations']['orders'][0]
        self.payments = [p for p in data['operations']['payments'] if p['orderId'] == self.order['_id']]
        self.invoice = data['billing']['invoices'][0]

    def test_distinct_measures_and_no_mutation(self):
        before = deepcopy([self.order, self.payments, self.invoice])
        self.assertEqual(order_collection_gap(self.order, self.payments), {
            'orderNumber':'ORD-1001', 'amount':'75.0', 'currency':'EUR', 'unit':'major', 'calculation':'order_collection_gap'})
        self.assertEqual(invoice_receivable(self.invoice), {
            'invoiceNumber':'INV-2001', 'amount':'95.00', 'currency':'EUR', 'unit':'major', 'calculation':'invoice_receivable'})
        self.assertEqual(before, [self.order, self.payments, self.invoice])

    def test_incompatible_evidence_is_rejected(self):
        for payment in [dict(self.payments[0], currency='USD'), dict(self.payments[0], orderId='another')]:
            with self.assertRaises(ValueError):
                order_collection_gap(self.order, [payment])
        with self.assertRaises(ValueError):
            order_collection_gap(self.order, self.payments + self.payments)
        with self.assertRaises(ValueError):
            order_collection_gap(self.order, [dict(self.payments[0], amount='NaN')])
        with self.assertRaises(ValueError):
            invoice_receivable(dict(self.invoice, cashAppliedMinor=True))

    def test_zero_balance_states_and_currency_scale(self):
        self.assertEqual(invoice_receivable(dict(self.invoice, status='void'))['amount'], '0')
        self.assertEqual(invoice_receivable(dict(self.invoice, currency='JPY'))['amount'], '9500')
        self.assertEqual(order_collection_gap(dict(self.order, status='cancelled'), self.payments)['amount'], '0')


if __name__ == '__main__':
    unittest.main()
