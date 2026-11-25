"""Feature switches, quick setup and what fills itself."""

import frappe
from frappe.tests import IntegrationTestCase, change_settings
from frappe.utils import add_days, today

from india_exim.exim_setup.quick_setup import get_setup, run_setup
from india_exim.features import FEATURES, extend_bootinfo
from india_exim.overrides.sales_invoice import make_export_shipment
from india_exim.tests.fixtures import (
	COMPANY,
	make_exchange_rate,
	make_export_invoice,
	make_import_invoice,
	make_incentive_rate,
	make_lut,
	make_tariff_item,
	setup_exim_company,
)
from india_exim.tests.test_imports_and_payments import make_bill_of_entry
from india_exim.utils.export_details import set_destination


class TestSimplifiedFlow(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		setup_exim_company()
		make_tariff_item()
		make_exchange_rate("USD", export_rate=80, import_rate=82)
		make_lut()
		make_incentive_rate("RoDTEP", 1)
		make_incentive_rate("Duty Drawback", 2)

	def test_switches_hide_modules_from_the_dock(self):
		row = lambda module: {"link_type": "Sidebar", "link_to": module}  # noqa: E731
		rows = [row("Exports"), row("Imports"), row("DGFT Licences")]
		with change_settings("India EXIM Settings", {"do_imports": 0, "use_dgft_licences": 1}):
			boot = frappe._dict(
				app_data=[
					{"app_name": "india_exim", "dock": list(rows)},
					{"app_name": "x", "dock": list(rows)},
				],
				dock={"india_exim": list(rows)},
			)
			extend_bootinfo(boot)
		self.assertFalse(boot.exim_features["imports"])
		self.assertTrue(boot.exim_features["licences"])
		expected = ["Exports", "DGFT Licences"]
		self.assertEqual([r["link_to"] for r in boot.app_data[0]["dock"]], expected)
		self.assertEqual([r["link_to"] for r in boot.dock["india_exim"]], expected)
		self.assertEqual(len(boot.app_data[1]["dock"]), 3)

	def test_quick_setup_can_be_run_again(self):
		settings = frappe.get_single("India EXIM Settings")
		before = {field: settings.get(field) for field in FEATURES}
		self.addCleanup(lambda: frappe.get_single("India EXIM Settings").update(before).save())
		values = {
			"company": COMPANY,
			"exim_iec": "aaqca8719h",
			"ad_code": "6390999",
			"port_code": "innsa1",
			"use_ecgc": 1,
			"do_imports": 1,
		}
		run_setup(values)
		run_setup(values)
		self.assertEqual(frappe.db.count("AD Code Registration", {"ad_code": "6390999"}), 1)
		known = get_setup(COMPANY)
		self.assertEqual(
			(known["exim_iec"], known["port_code"], known["use_ecgc"]), ("AAQCA8719H", "INNSA1", 1)
		)
		self.assertTrue(known["arn"])

		with self.set_user("Guest"):
			self.assertRaises(frappe.PermissionError, run_setup, values)

	def test_shipment_moves_by_itself(self):
		invoice = make_export_invoice()
		shipment = make_export_shipment(invoice.name)
		shipment.destination_country = "United States"
		shipment.insert()
		self.assertEqual(shipment.status, "Planned")

		shipment.booking_number = "BK1"
		shipment.save()
		self.assertEqual(shipment.status, "Booked")

		from india_exim.exports.doctype.export_shipment.export_shipment import make_shipping_bill

		bill = make_shipping_bill(shipment.name)
		bill.update({"shipping_bill_number": frappe.generate_hash(length=7).upper(), "port_code": "INNSA1"})
		bill.insert()
		bill.submit()
		bill.leo_date = today()
		bill.save()
		shipment.reload()
		self.assertEqual(shipment.status, "Customs Cleared")

		shipment.bl_number = "BL1"
		shipment.save()
		self.assertEqual(shipment.status, "Shipped")
		shipment.status = "Closed"
		shipment.flags.ignore_validate = True
		shipment.save()
		shipment.advance_status()
		self.assertEqual(shipment.status, "Closed")

	def test_destination_is_never_the_home_country(self):
		address = frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": frappe.generate_hash(length=8),
				"address_type": "Billing",
				"address_line1": "1 Dock Road",
				"city": "Dubai",
				"country": "United Arab Emirates",
				"gst_category": "Overseas",
			}
		).insert(ignore_permissions=True)
		doc = frappe.get_doc(
			{
				"doctype": "Sales Order",
				"company": COMPANY,
				"exim_is_export": 1,
				"exim_destination_country": "India",
				"customer_address": address.name,
			}
		)
		set_destination(doc)
		self.assertEqual(doc.exim_destination_country, "United Arab Emirates")
		doc.exim_destination_country = "Oman"  # the user's own choice stays
		set_destination(doc)
		self.assertEqual(doc.exim_destination_country, "Oman")

	def test_bill_of_entry_takes_bl_and_port_from_the_invoice(self):
		invoice = make_import_invoice()
		frappe.db.set_value(
			"Purchase Invoice",
			invoice.name,
			{"exim_bl_number": "BL-77", "exim_port_of_discharge": "innsa1"},
		)
		bill_of_entry = make_bill_of_entry(invoice)
		bill_of_entry.save()
		self.assertEqual((bill_of_entry.bill_of_lading_no, bill_of_entry.port_code), ("BL-77", "INNSA1"))

	def test_old_customs_rate_warns(self):
		from india_exim.utils.rates import warn_stale_exchange_rate

		make_exchange_rate("EUR", on=add_days(today(), -20))
		frappe.clear_messages()
		warn_stale_exchange_rate("EUR", add_days(today(), -10))
		self.assertFalse(frappe.get_message_log())
		warn_stale_exchange_rate("EUR", today())
		self.assertIn("customs exchange rate", str(frappe.get_message_log()))

	def test_saved_field_order_keeps_other_fields(self):
		from india_exim.setup.field_order import merge_order

		fields = [
			{"fieldname": "exim_a", "insert_after": "x"},
			{"fieldname": "exim_b", "insert_after": "exim_a"},
		]
		order = ["y", "exim_b", "x", "exim_old", "custom_z"]
		self.assertEqual(merge_order(order, fields), ["y", "x", "exim_a", "exim_b", "custom_z"])

	def test_prints_show_port_name_and_bank(self):
		from india_exim.utils.jinja import exim_bank_lines, exim_port

		self.assertIn("(INNSA1)", exim_port("INNSA1"))
		self.assertEqual((exim_port("XXXXXX"), exim_port(None)), ("XXXXXX", ""))
		bank = frappe.get_doc({"doctype": "Bank", "bank_name": frappe.generate_hash(length=8)}).insert()
		ad = frappe.get_doc(
			{
				"doctype": "AD Code Registration",
				"company": COMPANY,
				"ad_code": frappe.generate_hash(length=7),
				"port_code": "INMAA1",
				"bank": bank.name,
				"is_default": 1,
			}
		).insert()
		self.addCleanup(ad.delete)
		if not frappe.get_cached_doc("Company", COMPANY).get("bank_details_for_printing"):
			self.assertTrue(exim_bank_lines(COMPANY, "INMAA1"))

	def test_vgm_and_packing_list_on_the_checklist(self):
		invoice = make_export_invoice()
		shipment = make_export_shipment(invoice.name)
		shipment.update({"destination_country": "United States", "mode_of_transport": "Sea FCL"})
		shipment.insert()
		rows = {row.document_type: row for row in shipment.documents}
		self.assertEqual(rows["VGM Declaration (SOLAS)"].status, "Pending")
		shipment.append("containers", {"container_number": "MSKU1234565", "vgm_weight": 21000})
		shipment.save()
		rows = {row.document_type: row for row in shipment.documents}
		self.assertEqual(rows["VGM Declaration (SOLAS)"].status, "Received")

	def test_board_records_the_certificate_number(self):
		from india_exim.api.shipments import update_document

		shipment = make_export_shipment(make_export_invoice().name)
		shipment.update({"destination_country": "United States", "mode_of_transport": "Sea FCL"})
		shipment.insert()
		row = shipment.documents[0]
		update_document(shipment.name, row.name, "Received", document_number="C-1", document_date=today())
		shipment.reload()
		self.assertEqual(shipment.documents[0].document_number, "C-1")

	def test_igst_refund_finds_its_shipping_bills(self):
		from india_exim.export_incentives.doctype.gst_refund_claim.gst_refund_claim import (
			get_shipping_bills,
		)
		from india_exim.exports.doctype.shipping_bill.shipping_bill import make_shipping_bill

		bill = make_shipping_bill(make_export_invoice().name)
		bill.update(
			{
				"shipping_bill_number": frappe.generate_hash(length=7).upper(),
				"port_code": "INNSA1",
				"export_type": "With Payment of IGST",
			}
		)
		bill.items[0].igst_amount = 500
		bill.insert()
		bill.submit()
		bill.leo_date = today()
		bill.save()
		found = get_shipping_bills(COMPANY, add_days(today(), -1), today())
		self.assertIn(bill.name, found["shipping_bills"])
		self.assertGreaterEqual(found["igst"], 500)
