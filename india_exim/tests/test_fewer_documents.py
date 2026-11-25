"""Export without an Export Shipment, and the mistakes a real user makes on the way."""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, today

from india_exim.exports.doctype.shipping_bill.shipping_bill import (
	make_incentive_claims,
	make_shipping_bill,
)
from india_exim.features import extend_bootinfo
from india_exim.overrides.payment_entry import get_purpose_code
from india_exim.overrides.sales_invoice import make_export_shipment, validate_destination
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


class TestFewerDocuments(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		setup_exim_company()
		make_tariff_item()
		make_exchange_rate("USD", export_rate=80, import_rate=82)
		make_lut()
		make_incentive_rate("RoDTEP", 1)
		make_incentive_rate("Duty Drawback", 2)

	def make_bill(self, invoice=None, **values):
		bill = make_shipping_bill((invoice or make_export_invoice()).name)
		bill.update(
			{
				"shipping_bill_number": frappe.generate_hash(length=7).upper(),
				"port_code": "INNSA1",
				**values,
			}
		)
		return bill

	def messages(self):
		return " ".join(m.get("message", "") for m in frappe.get_message_log())

	def test_goods_go_on_shipping_bills_once(self):
		invoice = make_export_invoice(qty=10)
		first = self.make_bill(invoice)
		copy = self.make_bill(invoice)
		first.items[0].update({"qty": 4, "uqc_qty": 4, "invoice_value": 400})
		first.insert().submit()
		self.assertRaisesRegex(frappe.ValidationError, "already on", copy.insert)

		# the rest of the invoice can still be shipped
		rest = self.make_bill(invoice)
		self.assertEqual((rest.items[0].qty, rest.items[0].invoice_value), (6, 600))
		rest.insert().submit()
		self.assertRaisesRegex(frappe.ValidationError, "Everything on", make_shipping_bill, invoice.name)

		rest.cancel()
		self.assertEqual(make_shipping_bill(invoice.name).items[0].qty, 6)

	def test_customs_dates_are_not_in_the_future(self):
		self.assertRaisesRegex(
			frappe.ValidationError, "future", self.make_bill(leo_date=add_days(today(), 1)).insert
		)
		bill = self.make_bill().insert()
		bill.submit()
		bill.leo_date = add_days(today(), 1)
		self.assertRaisesRegex(frappe.ValidationError, "future", bill.save)

	def test_what_is_missing_is_said(self):
		frappe.clear_messages()
		self.make_bill(incoterm="CIF", port_code="INMAA1").insert()
		self.assertIn("No AD code is registered for port INMAA1", self.messages())
		self.assertIn("Freight / Insurance is zero", self.messages())
		frappe.clear_messages()
		self.make_bill(incoterm="FOB").insert()
		self.assertNotIn("is zero", self.messages())

	def test_shipment_made_later_takes_over_the_shipping_bill(self):
		invoice = make_export_invoice()
		bill = self.make_bill(invoice).insert()
		bill.submit()
		bill.update({"leo_date": today(), "bl_number": "BL77", "bl_date": today()})
		bill.save()

		shipment = make_export_shipment(invoice.name)
		shipment.destination_country = "United States"
		shipment.append("documents", {"document_type": "Shipping Bill"})
		shipment.insert()
		bill.reload()
		self.assertEqual(bill.export_shipment, shipment.name)
		self.assertEqual((shipment.bl_number, shipment.status), ("BL77", "Shipped"))
		row = next(row for row in shipment.documents if row.document_type == "Shipping Bill")
		self.assertEqual((row.status, row.document_number), ("Received", bill.shipping_bill_number))

		# a corrected number reaches the bill
		shipment.reload()
		shipment.bl_number = "BL78"
		shipment.save()
		self.assertEqual(frappe.db.get_value("Shipping Bill", bill.name, "bl_number"), "BL78")

	def test_shipping_bill_joins_an_existing_shipment(self):
		invoice = make_export_invoice()
		shipment = make_export_shipment(invoice.name)
		shipment.destination_country = "United States"
		shipment.insert()
		bill = self.make_bill(invoice).insert()
		self.assertEqual(bill.export_shipment, shipment.name)
		bill.submit()
		bill.update({"leo_date": today(), "bl_number": "BL9", "bl_date": today()})
		bill.save()
		self.assertEqual(frappe.db.get_value("Export Shipment", shipment.name, "bl_number"), "BL9")

	def test_drawback_entry_must_belong_to_the_goods(self):
		from india_exim.exports.doctype.shipping_bill.shipping_bill import get_drawback_entries

		tariff = make_tariff_item("63022190")
		serials = [row["value"] for row in get_drawback_entries(tariff)]
		self.assertIn("630201", serials)
		bill = self.make_bill()
		bill.items[0].update({"customs_tariff_item": tariff, "drawback_serial_no": "090101"})
		self.assertRaisesRegex(frappe.ValidationError, "not a drawback schedule entry", bill.insert)
		bill.items[0].drawback_serial_no = "630201"
		bill.insert()
		with self.set_user("Guest"):
			self.assertRaises(frappe.PermissionError, get_drawback_entries, tariff)

	def test_all_claims_in_one_go(self):
		bill = self.make_bill().insert()
		bill.submit()
		self.assertRaisesRegex(frappe.ValidationError, "Let Export Order", make_incentive_claims, bill.name)
		bill.leo_date = today()
		bill.save()
		claims = make_incentive_claims(bill.name)
		self.assertEqual({claim["scheme"] for claim in claims}, {"Duty Drawback", "RoDTEP"})
		self.assertTrue(all(claim["amount"] for claim in claims))
		self.assertEqual(make_incentive_claims(bill.name), [])

		with self.set_user("Guest"):
			self.assertRaises(frappe.PermissionError, make_incentive_claims, bill.name)

	def test_export_invoice_needs_a_destination(self):
		doc = frappe._dict(company=COMPANY, exim_is_export=1, _action="submit", gst_category="Overseas")
		self.assertRaisesRegex(frappe.ValidationError, "Destination Country", validate_destination, doc)
		doc.exim_destination_country = frappe.get_cached_value("Company", COMPANY, "country")
		self.assertRaisesRegex(frappe.ValidationError, "Destination Country", validate_destination, doc)
		doc.exim_destination_country = "United States"
		validate_destination(doc)

	def test_repeat_buyer_fills_itself(self):
		make_export_invoice(port_code="INMUN1", exim_mode_of_transport="Air")
		again = make_export_invoice(do_not_submit=1)
		self.assertEqual((again.port_code, again.exim_mode_of_transport), ("INMUN1", "Air"))

	def test_purpose_code_of_goods(self):
		invoice = make_export_invoice()
		payment = frappe._dict(
			party_type="Customer",
			party=FOREIGN_CUSTOMER,
			references=[frappe._dict(reference_doctype="Sales Invoice", reference_name=invoice.name)],
		)
		self.assertEqual(get_purpose_code(payment), "P0102")
		payment.references = []
		self.assertEqual(get_purpose_code(payment), "P0103")

	def test_shipments_switched_off_leave_the_menu(self):
		settings = frappe.get_single("India EXIM Settings")
		before = settings.track_shipments
		self.addCleanup(
			lambda: frappe.get_single("India EXIM Settings").update({"track_shipments": before}).save()
		)
		for value, expected in ((1, 2), (0, 1)):
			settings = frappe.get_single("India EXIM Settings").update({"track_shipments": value})
			settings.save()
			boot = frappe._dict(
				module_sidebars={
					"Exports": {"items": [{"link_to": "Export Shipment"}, {"link_to": "Shipping Bill"}]}
				}
			)
			extend_bootinfo(boot)
			self.assertEqual(len(boot.module_sidebars["Exports"]["items"]), expected)
