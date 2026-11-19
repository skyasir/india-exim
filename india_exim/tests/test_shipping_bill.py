import frappe
from frappe.tests import IntegrationTestCase, change_settings
from frappe.utils import add_months, getdate, today

from india_exim.tests.fixtures import (
	COMPANY,
	FOREIGN_CUSTOMER,
	make_exchange_rate,
	make_export_invoice,
	make_incentive_rate,
	make_lut,
	make_tariff_item,
	setup_exim_company,
)


class TestShippingBill(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		setup_exim_company()
		make_tariff_item()
		make_exchange_rate("USD", export_rate=80, import_rate=82)
		make_lut()
		make_incentive_rate("RoDTEP", 2, cap=5)
		make_incentive_rate("Duty Drawback", 1.5)

	def make_shipping_bill(self, invoice, **values):
		from india_exim.exports.doctype.shipping_bill.shipping_bill import make_shipping_bill

		shipping_bill = make_shipping_bill(invoice.name)
		shipping_bill.update(
			{
				"shipping_bill_number": frappe.generate_hash(length=7).upper(),
				"shipping_bill_date": today(),
				"port_code": "INNSA1",
				**values,
			}
		)
		return shipping_bill

	def test_export_invoice_without_lut_is_blocked(self):
		frappe.db.delete("Letter of Undertaking", {"company": COMPANY})
		try:
			self.assertRaisesRegex(frappe.ValidationError, "Letter of Undertaking", make_export_invoice)
		finally:
			make_lut()

	def test_export_invoice_links_valid_lut(self):
		invoice = make_export_invoice()
		self.assertEqual(invoice.exim_lut, frappe.db.get_value("Letter of Undertaking", {"company": COMPANY}))

	def test_fob_and_incentives_with_cap(self):
		invoice = make_export_invoice(qty=10, rate=100)
		shipping_bill = self.make_shipping_bill(invoice, incoterm="CIF", freight=50, insurance=10)
		shipping_bill.insert()

		self.assertEqual(shipping_bill.customs_exchange_rate, 80)
		self.assertEqual(shipping_bill.total_fob_value, 940)
		self.assertEqual(shipping_bill.total_fob_value_inr, 75200)
		# RoDTEP: 2% of 75,200 = 1,504 but capped at 5 x 10 units = 50
		self.assertEqual(shipping_bill.total_rodtep, 50)
		# Drawback: 1.5% of 75,200, no cap
		self.assertEqual(shipping_bill.total_drawback, 1128)

	def test_fob_incoterm_rejects_freight_deduction(self):
		invoice = make_export_invoice()
		shipping_bill = self.make_shipping_bill(invoice, incoterm="FOB", freight=10)
		self.assertRaises(frappe.ValidationError, shipping_bill.insert)

	def test_duplicate_shipping_bill_number_at_port(self):
		invoice = make_export_invoice()
		first = self.make_shipping_bill(invoice)
		first.insert()
		second = self.make_shipping_bill(invoice, shipping_bill_number=first.shipping_bill_number)
		self.assertRaises(frappe.ValidationError, second.insert)

	def test_realisation_due_date_follows_settings(self):
		invoice = make_export_invoice()
		shipping_bill = self.make_shipping_bill(invoice).insert()
		self.assertEqual(getdate(shipping_bill.realisation_due_date), getdate(add_months(today(), 9)))
		self.assertEqual(shipping_bill.outstanding_value, shipping_bill.total_invoice_value)

	@change_settings("India EXIM Settings", {"incentive_accrual_point": "On LEO"})
	def test_leo_accrues_incentives_and_cancel_reverses(self):
		invoice = make_export_invoice(qty=10, rate=100)
		shipping_bill = self.make_shipping_bill(invoice).insert()
		shipping_bill.submit()
		self.assertEqual(shipping_bill.status, "Filed")
		self.assertFalse(shipping_bill.accrual_journal_entry)

		shipping_bill.leo_date = today()
		shipping_bill.save()
		shipping_bill.reload()
		self.assertEqual(shipping_bill.status, "LEO Granted")
		self.assertTrue(shipping_bill.accrual_journal_entry)

		entries = frappe.get_all(
			"Journal Entry Account",
			filters={"parent": shipping_bill.accrual_journal_entry},
			fields=["account", "debit", "credit"],
		)
		company = frappe.get_cached_doc("Company", COMPANY)
		balances = {row.account: row.debit - row.credit for row in entries}
		self.assertEqual(balances[company.exim_rodtep_receivable_account], 50)
		self.assertEqual(balances[company.exim_rodtep_income_account], -50)
		self.assertEqual(balances[company.exim_drawback_receivable_account], 1200)

		shipping_bill.cancel()
		self.assertEqual(
			frappe.db.get_value("Journal Entry", shipping_bill.accrual_journal_entry, "docstatus"), 2
		)

	def test_leo_before_shipping_bill_date_rejected(self):
		invoice = make_export_invoice()
		shipping_bill = self.make_shipping_bill(invoice, leo_date="2000-01-01")
		self.assertRaises(frappe.ValidationError, shipping_bill.insert)

	def test_submit_fills_empty_invoice_shipping_bill_fields(self):
		invoice = make_export_invoice()
		shipping_bill = self.make_shipping_bill(invoice).insert()
		shipping_bill.submit()
		details = frappe.db.get_value(
			"Sales Invoice", invoice.name, ["shipping_bill_number", "port_code"], as_dict=True
		)
		self.assertEqual(details.shipping_bill_number, shipping_bill.shipping_bill_number)
		self.assertEqual(details.port_code, "INNSA1")

	def test_item_defaults_tariff_from_eight_digit_hsn(self):
		item = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": "_Test EXIM HSN Default",
				"item_group": "All Item Groups",
				"stock_uom": "Nos",
				"gst_hsn_code": "52083190",
			}
		).insert()
		self.assertEqual(item.exim_customs_tariff_item, "52083190")

	def test_freight_and_insurance_come_from_invoice_exim_tab(self):
		invoice = make_export_invoice(
			qty=10, rate=100, incoterm="CIF", exim_freight=50, exim_insurance=10, port_code="INNSA1"
		)
		shipping_bill = self.make_shipping_bill(invoice).insert()
		self.assertEqual(shipping_bill.freight, 50)
		self.assertEqual(shipping_bill.insurance, 10)
		self.assertEqual(shipping_bill.total_fob_value, 940)
		shipping_bill.submit()
		self.assertEqual(
			frappe.db.get_value("Sales Invoice", invoice.name, "shipping_bill_number"),
			shipping_bill.shipping_bill_number,
		)
