"""Advance Authorisation and EPCG: imports debited, duty foregone, export obligation credited."""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, add_months, flt, getdate, today

from india_exim.tests.fixtures import (
	COMPANY,
	TARIFF_CODE,
	make_exchange_rate,
	make_export_invoice,
	make_import_invoice,
	make_incentive_rate,
	make_lut,
	make_tariff_item,
	setup_exim_company,
)
from india_exim.tests.test_imports_and_payments import make_bill_of_entry


def make_authorisation(scheme="Advance Authorisation", **values):
	doc = frappe.get_doc(
		{
			"doctype": "Export Authorisation",
			"scheme": scheme,
			"company": COMPANY,
			"authorisation_number": frappe.generate_hash(length=10).upper(),
			"authorisation_date": add_days(today(), -10),
			"imports": [{"customs_tariff_item": TARIFF_CODE, "qty_allowed": 25, "cif_allowed": 300000}],
			"exports": [{"customs_tariff_item": TARIFF_CODE, "qty_required": 15, "fob_required": 100000}],
			**values,
		}
	)
	return doc.insert()


def make_export(authorisation, qty=10, rate=100):
	from india_exim.exports.doctype.shipping_bill.shipping_bill import make_shipping_bill

	invoice = make_export_invoice(qty=qty, rate=rate)
	shipping_bill = make_shipping_bill(invoice.name)
	shipping_bill.update(
		{
			"shipping_bill_number": frappe.generate_hash(length=7).upper(),
			"shipping_bill_date": today(),
			"port_code": "INNSA1",
			"export_authorisation": authorisation,
		}
	)
	shipping_bill.insert()
	shipping_bill.submit()
	return shipping_bill


class TestAuthorisations(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		setup_exim_company()
		make_tariff_item(bcd=10, sws=10)
		make_exchange_rate("USD", export_rate=80, import_rate=82)
		make_lut()
		make_incentive_rate("RoDTEP", 1)
		make_incentive_rate("Duty Drawback", 2)

	def test_advance_authorisation_defaults(self):
		licence = make_authorisation()
		self.assertEqual(
			getdate(licence.import_validity_upto), getdate(add_months(licence.authorisation_date, 12))
		)
		self.assertEqual(getdate(licence.eo_period_upto), getdate(add_months(licence.authorisation_date, 18)))
		self.assertEqual((licence.eo_required, licence.status), (100000, "Active"))

	def test_import_under_licence_records_duty_foregone_and_debits_licence(self):
		licence = make_authorisation()
		invoice = make_import_invoice(qty=10, rate=100)
		bill_of_entry = make_bill_of_entry(invoice, exim_authorisation=licence.name)
		bill_of_entry.save()
		item = bill_of_entry.items[0]
		self.assertEqual(item.assessable_value, 82000)
		self.assertEqual(item.customs_duty, 0)
		self.assertEqual(item.exim_duty_foregone, 9020)  # BCD 10% + SWS 10% of BCD
		bill_of_entry.submit()

		licence.reload()
		row = licence.imports[0]
		self.assertEqual((row.qty_imported, row.cif_imported), (10, 82000))
		self.assertEqual(licence.total_duty_saved, bill_of_entry.exim_total_duty_foregone)

		# more than the quantity left is refused
		over = make_bill_of_entry(make_import_invoice(qty=20, rate=100), exim_authorisation=licence.name)
		self.assertRaisesRegex(frappe.ValidationError, "is left under", over.save)

		bill_of_entry.cancel()
		licence.reload()
		self.assertEqual(licence.imports[0].qty_imported, 0)

	def test_igst_is_exempt_under_licence_unless_paid(self):
		licence = make_authorisation()
		bill_of_entry = make_bill_of_entry(make_import_invoice(), exim_authorisation=licence.name)
		bill_of_entry.save()
		charged = bill_of_entry.total_taxes
		bill_of_entry.exim_igst_exempt = 1
		bill_of_entry.save()
		self.assertEqual(bill_of_entry.total_taxes, 0)
		self.assertEqual(bill_of_entry.total_amount_payable, 0)
		# 18% IGST on 82,000 + 9,020 customs duty foregone
		self.assertEqual(bill_of_entry.items[0].exim_igst_foregone, 16383.6)
		bill_of_entry.submit()
		licence.reload()
		self.assertEqual(licence.total_duty_saved, 25403.6)

		paid = make_bill_of_entry(make_import_invoice(), exim_authorisation=licence.name)
		paid.exim_igst_exempt = 0
		paid.save()
		self.assertGreater(paid.total_taxes, 0)
		self.assertEqual(paid.items[0].exim_igst_foregone, 0)
		self.assertIsNotNone(charged)

	def test_one_bill_part_under_licence_part_duty_paid(self):
		licence = make_authorisation()
		bill = make_bill_of_entry(make_import_invoice(qty=10, rate=100))
		row = bill.items[0]
		row.qty, row.exim_authorisation = 6, licence.name
		other = {k: v for k, v in row.as_dict().items() if k not in ("name", "idx", "parent")}
		bill.append("items", {**other, "qty": 4, "exim_authorisation": None, "name": None})
		bill.exim_igst_exempt = 1
		bill.save()
		under, paid = bill.items
		self.assertEqual((under.customs_duty, paid.customs_duty), (0, 3608))  # 32,800 at 11%
		self.assertEqual(flt(bill.total_taxes, 2), flt((32800 + 3608) * 0.18, 2))
		self.assertGreater(under.exim_igst_foregone, 0)
		self.assertEqual(paid.exim_igst_foregone, 0)
		bill.submit()
		licence.reload()
		self.assertEqual(licence.imports[0].qty_imported, 6)

		# the parts together cannot exceed the invoice
		over = make_bill_of_entry(make_import_invoice(qty=10, rate=100))
		row = over.items[0]
		row.exim_authorisation = licence.name
		over.append("items", {**other, "pi_detail": row.pi_detail, "purchase_invoice": row.purchase_invoice})
		self.assertRaisesRegex(frappe.ValidationError, "together", over.save)

	def test_header_licence_fills_and_clears_rows(self):
		licence = make_authorisation()
		bill = make_bill_of_entry(make_import_invoice(), exim_authorisation=licence.name)
		bill.save()
		self.assertEqual(bill.items[0].exim_authorisation, licence.name)
		bill.exim_authorisation = None
		bill.save()
		self.assertFalse(bill.items[0].exim_authorisation)

	def test_licence_limits(self):
		licence = make_authorisation(
			imports=[{"customs_tariff_item": TARIFF_CODE, "qty_allowed": 10, "cif_allowed": 50000}]
		)
		invoice = make_import_invoice(qty=20)
		bill_of_entry = make_bill_of_entry(invoice, exim_authorisation=licence.name)
		bill_of_entry.items[0].qty = 10
		frappe.clear_messages()
		bill_of_entry.save()
		self.assertIn("CIF value", str(frappe.get_message_log()))

		# two rows of one item count together
		row = bill_of_entry.items[0].as_dict()
		for field in ("name", "idx", "parent"):
			row.pop(field, None)
		bill_of_entry.append("items", row)
		self.assertRaisesRegex(frappe.ValidationError, "is left under", bill_of_entry.save)

	def test_import_after_validity_is_refused(self):
		licence = make_authorisation(
			authorisation_date=add_months(today(), -14), import_validity_upto=add_days(today(), -1)
		)
		bill_of_entry = make_bill_of_entry(make_import_invoice(), exim_authorisation=licence.name)
		self.assertRaisesRegex(frappe.ValidationError, "were allowed until", bill_of_entry.save)

	def test_exports_discharge_obligation_without_incentives(self):
		licence = make_authorisation()
		shipping_bill = make_export(licence.name, qty=10, rate=100)  # FOB 1,000 USD x 80 = 80,000
		self.assertEqual((shipping_bill.total_drawback, shipping_bill.total_rodtep), (0, 0))

		licence.reload()
		self.assertEqual(licence.eo_fulfilled, 80000)
		self.assertEqual(licence.eo_percent, 80)
		self.assertEqual(licence.status, "Active")

		make_export(licence.name, qty=10, rate=100)
		licence.reload()
		self.assertEqual(licence.status, "EO Fulfilled")  # 1,60,000 FOB and 20 of 15 units

		licence.eodc_number = "EODC/TEST/1"
		licence.eodc_date = today()
		licence.save()
		self.assertEqual(licence.status, "Redeemed")

	def test_licence_that_allows_incentives_keeps_them(self):
		licence = make_authorisation(drawback_admissible=1, rodtep_admissible=1)
		shipping_bill = make_export(licence.name)
		self.assertEqual((shipping_bill.total_drawback, shipping_bill.total_rodtep), (1600, 800))

	def test_epcg_obligation_is_a_multiple_of_duty_saved(self):
		licence = make_authorisation(scheme="EPCG", exports=[{"customs_tariff_item": TARIFF_CODE}])
		self.assertEqual(getdate(licence.eo_period_upto), getdate(add_months(licence.authorisation_date, 72)))
		self.assertEqual(getdate(licence.block_1_upto), getdate(add_months(licence.authorisation_date, 48)))

		bill_of_entry = make_bill_of_entry(
			make_import_invoice(qty=10, rate=100), exim_authorisation=licence.name
		)
		bill_of_entry.save()
		bill_of_entry.submit()
		licence.reload()
		self.assertAlmostEqual(licence.eo_required, licence.total_duty_saved * 6, places=2)
		self.assertGreater(licence.eo_required, 0)

	def test_register_report(self):
		from frappe.desk.query_report import run

		licence = make_authorisation()
		rows = [
			r
			for r in run("Authorisation Register", filters={"company": COMPANY})["result"]
			if isinstance(r, dict)
		]
		self.assertIn(licence.name, [row["name"] for row in rows])
