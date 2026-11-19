import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import getdate

from india_exim.tests.fixtures import make_exchange_rate, make_incentive_rate, make_tariff_item
from india_exim.utils.rates import get_customs_exchange_rate, get_incentive_rate, get_tariff_rate


class TestRates(IntegrationTestCase):
	def test_tariff_code_must_have_eight_digits(self):
		doc = frappe.get_doc(
			{"doctype": "Customs Tariff Item", "tariff_code": "5208", "description": "short"}
		)
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_tariff_rates_cannot_overlap(self):
		doc = frappe.get_doc(
			{
				"doctype": "Customs Tariff Item",
				"tariff_code": "52084200",
				"description": "overlap",
				"rates": [
					{"effective_from": "2024-01-01", "effective_to": "2024-12-31", "bcd_rate": 10},
					{"effective_from": "2024-06-01", "bcd_rate": 20},
				],
			}
		)
		self.assertRaises(frappe.ValidationError, doc.insert)

	def test_tariff_rate_picks_period_in_force(self):
		code = "52084300"
		frappe.get_doc(
			{
				"doctype": "Customs Tariff Item",
				"tariff_code": code,
				"description": "periods",
				"rates": [
					{"effective_from": "2024-01-01", "effective_to": "2024-12-31", "bcd_rate": 10},
					{"effective_from": "2025-01-01", "bcd_rate": 20},
				],
			}
		).insert()
		self.assertEqual(get_tariff_rate(code, "2024-07-01").bcd_rate, 10)
		self.assertEqual(get_tariff_rate(code, "2026-07-01").bcd_rate, 20)
		self.assertRaises(frappe.ValidationError, get_tariff_rate, code, "2023-12-31")

	def test_incentive_rate_lookup_and_overlap(self):
		make_tariff_item()
		make_incentive_rate("RoDTEP", 2, effective_from="2001-01-01")
		self.assertEqual(get_incentive_rate("RoDTEP", "52083190", "2001-06-01").rate, 2)
		self.assertIsNone(get_incentive_rate("RoDTEP", "52083190", "2000-06-01"))
		duplicate = frappe.get_doc(
			{
				"doctype": "Export Incentive Rate",
				"scheme": "RoDTEP",
				"customs_tariff_item": "52083190",
				"rate": 3,
				"effective_from": "2002-01-01",
			}
		)
		self.assertRaises(frappe.ValidationError, duplicate.insert)

	def test_customs_exchange_rate(self):
		make_exchange_rate("EUR", export_rate=90, import_rate=92, on="2001-01-01")
		self.assertEqual(get_customs_exchange_rate("EUR", "2001-02-01", "Export"), 90)
		self.assertEqual(get_customs_exchange_rate("EUR", "2001-02-01", "Import"), 92)
		self.assertEqual(get_customs_exchange_rate("INR", getdate()), 1)
		self.assertRaises(frappe.ValidationError, get_customs_exchange_rate, "EUR", "2000-12-31")
