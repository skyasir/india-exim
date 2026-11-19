import frappe
from frappe.tests import IntegrationTestCase, change_settings
from frappe.utils import add_days, today

from india_exim.tests.fixtures import (
	make_exchange_rate,
	make_export_invoice,
	make_import_invoice,
	make_lut,
	make_payment,
	make_tariff_item,
	setup_exim_company,
)


def make_bill_of_entry(purchase_invoice, **values):
	from india_compliance.gst_india.doctype.bill_of_entry.bill_of_entry import make_bill_of_entry

	bill_of_entry = make_bill_of_entry(purchase_invoice.name)
	bill_of_entry.bill_of_entry_no = frappe.generate_hash(length=7)
	bill_of_entry.bill_of_entry_date = today()
	bill_of_entry.update(values)
	return bill_of_entry


class TestImportsAndPayments(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		setup_exim_company()
		make_tariff_item(bcd=10, sws=10)
		make_exchange_rate("USD", export_rate=80, import_rate=82)
		make_lut()

	@change_settings("India EXIM Settings", {"capitalise_customs_duty": 1})
	def test_duty_breakup_feeds_india_compliance_and_landed_cost(self):
		invoice = make_import_invoice(qty=10, rate=100)
		bill_of_entry = make_bill_of_entry(invoice, exim_additional_value=1000)
		bill_of_entry.save()

		item = bill_of_entry.items[0]
		self.assertEqual(bill_of_entry.exim_customs_exchange_rate, 82)
		self.assertEqual(item.assessable_value, 83000)  # 1,000 USD x 82 + 1,000 freight
		self.assertEqual(item.exim_bcd_amount, 8300)
		self.assertEqual(item.exim_sws_amount, 830)
		self.assertEqual(item.customs_duty, 9130)
		self.assertEqual(item.taxable_value, 92130)  # India Compliance: assessable + customs duty

		bill_of_entry.submit()
		self.assertTrue(bill_of_entry.exim_landed_cost_voucher)
		voucher = frappe.get_doc("Landed Cost Voucher", bill_of_entry.exim_landed_cost_voucher)
		self.assertEqual(voucher.docstatus, 1)
		self.assertEqual(voucher.total_taxes_and_charges, 9130)

		bill_of_entry.cancel()
		self.assertEqual(frappe.db.get_value("Landed Cost Voucher", voucher.name, "docstatus"), 2)

	def test_manual_rates_for_exemption(self):
		invoice = make_import_invoice()
		bill_of_entry = make_bill_of_entry(invoice)
		bill_of_entry.items[0].exim_manual_rates = 1
		bill_of_entry.items[0].exim_bcd_rate = 0
		bill_of_entry.items[0].exim_sws_rate = 0
		bill_of_entry.items[0].exim_exemption_notification = "TEST/2026"
		bill_of_entry.save()
		self.assertEqual(bill_of_entry.items[0].customs_duty, 0)

	def test_import_payment_status_follows_payment_entries(self):
		invoice = make_import_invoice(qty=10, rate=100)
		bill_of_entry = make_bill_of_entry(invoice)
		bill_of_entry.save()
		bill_of_entry.submit()
		bill_of_entry.reload()
		self.assertEqual(bill_of_entry.exim_payment_status, "Unpaid")
		self.assertEqual(bill_of_entry.exim_invoice_value, 1000)

		make_payment(invoice, 400)
		bill_of_entry.reload()
		self.assertEqual(bill_of_entry.exim_payment_status, "Partly Paid")
		self.assertEqual(bill_of_entry.exim_paid_value, 400)

		make_payment(invoice, 600)
		bill_of_entry.reload()
		self.assertEqual(bill_of_entry.exim_payment_status, "Paid")

	def test_export_realisation_follows_payments_credit_notes_and_write_off(self):
		from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return

		from india_exim.exports.doctype.shipping_bill.shipping_bill import make_shipping_bill

		invoice = make_export_invoice(qty=10, rate=100)
		shipping_bill = make_shipping_bill(invoice.name)
		shipping_bill.update(
			{
				"shipping_bill_number": frappe.generate_hash(length=7),
				"shipping_bill_date": today(),
				"port_code": "INNSA1",
			}
		)
		shipping_bill.insert()
		shipping_bill.submit()
		shipping_bill.reload()
		self.assertEqual(shipping_bill.realisation_status, "Pending")
		self.assertEqual(shipping_bill.outstanding_value, 1000)

		payment = make_payment(invoice, 600)
		shipping_bill.reload()
		self.assertEqual(shipping_bill.realisation_status, "Partly Realised")
		self.assertEqual(shipping_bill.realised_value, 600)

		credit_note = make_sales_return(invoice.name)
		credit_note.items[0].qty = -1
		credit_note.insert()
		credit_note.submit()
		shipping_bill.reload()
		self.assertEqual(shipping_bill.credit_note_value, 100)
		self.assertEqual(shipping_bill.outstanding_value, 300)

		payment.cancel()
		shipping_bill.reload()
		self.assertEqual(shipping_bill.realised_value, 0)
		self.assertEqual(shipping_bill.outstanding_value, 900)

		shipping_bill.append(
			"realisation_actions",
			{
				"action_type": "Extension",
				"approved_by": "AD Bank",
				"approval_reference": "EXT-1",
				"approval_date": today(),
				"extended_upto": add_days(shipping_bill.realisation_due_date, 90),
			},
		)
		shipping_bill.append(
			"realisation_actions",
			{
				"action_type": "Write-off",
				"approved_by": "AD Bank",
				"approval_reference": "WO-1",
				"approval_date": today(),
				"write_off_value": 900,
			},
		)
		original_due = shipping_bill.realisation_due_date
		shipping_bill.save()
		shipping_bill.reload()
		self.assertEqual(shipping_bill.realisation_status, "Written Off")
		self.assertEqual(shipping_bill.realisation_due_date, add_days(original_due, 90))
