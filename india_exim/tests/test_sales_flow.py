"""Quotation -> Sales Order -> Proforma Invoice for an export order."""

import frappe
from erpnext.selling.doctype.quotation.quotation import make_sales_order
from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate

from india_exim.tests.fixtures import (
	COMPANY,
	FOREIGN_CUSTOMER,
	TARIFF_CODE,
	make_export_item,
	make_lut,
	make_party_account,
	setup_exim_company,
)
from india_exim.utils import render_print_format

EXPORT_DETAILS = {
	"exim_destination_country": "United States",
	"exim_port_of_discharge": "New York",
	"exim_final_destination": "Chicago",
	"exim_payment_terms_type": "Letter of Credit",
	"exim_lc_number": "LC-TEST-001",
	"exim_marks_and_numbers": "ACME/NY/1-10",
}


def make_export_quotation(**details):
	quotation = frappe.get_doc(
		{
			"doctype": "Quotation",
			"company": COMPANY,
			"quotation_to": "Customer",
			"party_name": FOREIGN_CUSTOMER,
			"transaction_date": getdate(),
			"currency": "USD",
			"conversion_rate": 83,
			"incoterm": "FOB",
			"items": [{"item_code": make_export_item(), "qty": 10, "rate": 100}],
			**details,
		}
	)
	return quotation.insert(ignore_permissions=True)


class TestSalesFlow(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		setup_exim_company()
		make_lut()
		frappe.db.set_single_value("Selling Settings", "enable_proforma_invoice", 1)

	def test_quotation_ticks_is_export_from_customer(self):
		self.assertEqual(make_export_quotation().exim_is_export, 1)

	def test_export_details_flow_to_sales_order_and_proforma(self):
		quotation = make_export_quotation(**EXPORT_DETAILS)
		quotation.submit()

		order = make_sales_order(quotation.name)
		order.delivery_date = add_days(getdate(), 30)
		order.po_no = "PO-ACME-7"
		order.debit_to = make_party_account("USD", "Receivable")
		order.insert(ignore_permissions=True)
		self.assertEqual(order.exim_is_export, 1)
		for fieldname, value in EXPORT_DETAILS.items():
			self.assertEqual(order.get(fieldname), value, fieldname)
		order.submit()

		proforma = frappe.get_doc(
			{
				"doctype": "Proforma Invoice",
				"sales_order": order.name,
				"print_format": "Export Proforma Invoice",
				"items": [{"so_detail": order.items[0].name, "qty": 4}],
			}
		).insert(ignore_permissions=True)

		html = render_print_format(proforma.get_sales_order_copy(), "Export Proforma Invoice")
		for text in (
			"PROFORMA INVOICE",
			proforma.name,
			"AAQCA8719H",
			TARIFF_CODE,
			"New York",
			"LC-TEST-001",
			"PO-ACME-7",
		):
			self.assertIn(text, html)
		# only the proformed quantity: 4 x 100
		self.assertIn("400", html)
		self.assertNotIn("1,000", html)

	def test_export_details_flow_through_delivery_note_to_invoice(self):
		quotation = make_export_quotation(**EXPORT_DETAILS)
		quotation.submit()
		order = make_sales_order(quotation.name)
		order.delivery_date = add_days(getdate(), 30)
		order.insert(ignore_permissions=True)
		order.submit()

		delivery = make_delivery_note(order.name)
		delivery.insert(ignore_permissions=True)
		self.assertEqual(delivery.exim_is_export, 1)
		for fieldname, value in EXPORT_DETAILS.items():
			self.assertEqual(delivery.get(fieldname), value, fieldname)

		delivery.submit()

		# a delivery note without the details (made before the tab existed) still passes them on
		frappe.db.set_value("Delivery Note", delivery.name, dict.fromkeys(EXPORT_DETAILS))
		invoice = make_sales_invoice(delivery.name)
		invoice.debit_to = make_party_account("USD", "Receivable")
		invoice.insert(ignore_permissions=True)
		for fieldname, value in EXPORT_DETAILS.items():
			self.assertEqual(invoice.get(fieldname), value, fieldname)

	def test_shipping_bill_from_shipment_deducts_freight_and_claims_incentives(self):
		from india_exim.exports.doctype.export_shipment.export_shipment import make_shipping_bill
		from india_exim.overrides.sales_invoice import make_export_shipment
		from india_exim.tests.fixtures import make_export_invoice

		invoice = make_export_invoice(
			qty=10, rate=100, incoterm="CIF", exim_freight=50, exim_insurance=10, do_not_submit=True
		)
		invoice.exim_is_export = 1
		invoice.save()
		invoice.submit()
		shipment = make_export_shipment(invoice.name)
		shipment.insert(ignore_permissions=True)

		shipping_bill = make_shipping_bill(shipment.name)
		self.assertEqual((shipping_bill.freight, shipping_bill.insurance), (50, 10))
		# rows reach the browser as plain values, so the claim ticks must be set, not defaulted
		row = shipping_bill.items[0].as_dict()
		self.assertEqual((row.claim_drawback, row.claim_rodtep), (1, 1))
