"""Import Shipment: orders and invoices join it, its status and their transport details follow."""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, today

from india_exim.imports.doctype.import_shipment.import_shipment import make_from_purchase_invoice
from india_exim.tests.fixtures import (
	COMPANY,
	make_exchange_rate,
	make_import_invoice,
	make_import_item,
	make_tariff_item,
	setup_exim_company,
)
from india_exim.tests.test_imports_and_payments import make_bill_of_entry


class TestImportShipment(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		setup_exim_company()
		make_tariff_item(bcd=10, sws=10)
		make_exchange_rate("USD", export_rate=80, import_rate=82)
		frappe.db.set_value("Supplier", "_Test Foreign Supplier", "country", "United States")

	def make_shipment(self, invoice=None):
		shipment = make_from_purchase_invoice((invoice or make_import_invoice()).name)
		shipment.insert()
		return shipment

	def test_status_and_invoice_follow_the_shipment(self):
		invoice = make_import_invoice()
		shipment = self.make_shipment(invoice)
		self.assertEqual((shipment.status, shipment.origin_country), ("Planned", "United States"))

		shipment.booking_number = "BK-1"
		shipment.save()
		self.assertEqual(shipment.status, "Booked")
		shipment.update({"bl_number": "BL-9", "bl_date": today(), "port_of_discharge": "INNSA1"})
		shipment.save()
		self.assertEqual(shipment.status, "Shipped")
		shipment.update({"ata": today(), "free_days": 14})
		shipment.save()
		self.assertEqual(shipment.status, "Arrived")
		self.assertEqual(getdate(shipment.free_time_ends), getdate(add_days(today(), 14)))

		invoice.reload()
		self.assertEqual(
			(invoice.exim_import_shipment, invoice.exim_bl_number, getdate(invoice.exim_free_time_ends)),
			(shipment.name, "BL-9", getdate(add_days(today(), 14))),
		)
		bill = make_bill_of_entry(invoice)
		bill.save()
		self.assertEqual((bill.bill_of_lading_no, bill.port_code), ("BL-9", "INNSA1"))
		bill.submit()
		shipment.reload()
		self.assertEqual(shipment.status, "Customs Cleared")

	def test_part_cleared_is_not_cleared(self):
		invoice = make_import_invoice(qty=10)
		shipment = self.make_shipment(invoice)
		bill = make_bill_of_entry(invoice)
		bill.items[0].qty = 4
		bill.save()
		bill.submit()
		shipment.reload()
		self.assertEqual(shipment.status, "Planned")

	def test_invoice_is_on_one_shipment(self):
		invoice = make_import_invoice()
		self.make_shipment(invoice)
		self.assertRaisesRegex(frappe.ValidationError, "already on", self.make_shipment, invoice)

	def test_invoice_of_an_order_joins_its_shipment(self):
		from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_invoice

		from india_exim.imports.doctype.import_shipment.import_shipment import make_from_purchase_order

		warehouse = frappe.db.get_value("Warehouse", {"company": COMPANY, "is_group": 0})
		order = frappe.get_doc(
			{
				"doctype": "Purchase Order",
				"company": COMPANY,
				"supplier": "_Test Foreign Supplier",
				"currency": "USD",
				"conversion_rate": 83,
				"exim_is_import": 1,
				"schedule_date": add_days(today(), 10),
				"items": [
					{
						"item_code": make_import_item(),
						"qty": 5,
						"rate": 10,
						"warehouse": warehouse,
						"schedule_date": add_days(today(), 10),
					}
				],
			}
		).insert()
		order.submit()
		shipment = make_from_purchase_order(order.name)
		shipment.bl_number = "BL-ORD"
		shipment.insert()
		self.assertEqual(shipment.status, "Shipped")

		from india_exim.tests.fixtures import make_party_account

		invoice = make_purchase_invoice(order.name)
		invoice.update(
			{
				"exim_is_import": 1,
				"credit_to": make_party_account("USD", "Payable"),
				"bill_no": "X-1",
				"bill_date": today(),
			}
		)
		invoice.insert()
		invoice.submit()
		shipment.reload()
		self.assertEqual([row.purchase_invoice for row in shipment.invoices], [invoice.name])
		invoice.reload()
		self.assertEqual(invoice.exim_bl_number, "BL-ORD")
		invoice.cancel()
		shipment.reload()
		self.assertFalse(shipment.invoices)
