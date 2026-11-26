"""Certificates of Origin (RVC from the BOM) and concessional duty claimed on Bills of Entry."""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_months, getdate, today

from india_exim.tests.fixtures import (
	COMPANY,
	FOREIGN_CUSTOMER,
	TARIFF_CODE,
	make_exchange_rate,
	make_import_invoice,
	make_tariff_item,
	setup_exim_company,
)
from india_exim.tests.test_imports_and_payments import make_bill_of_entry

UAE = "India-UAE CEPA"
PRODUCT = "_Test EXIM Woven Fabric"


def make_item(code: str, tariff: str | None = None, country: str | None = None) -> str:
	if not frappe.db.exists("Item", code):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": code,
				"item_group": "All Item Groups",
				"stock_uom": "Nos",
				"is_stock_item": 1,
				"exim_customs_tariff_item": tariff and make_tariff_item(tariff),
				"country_of_origin": country,
				"gst_hsn_code": "52083190",
			}
		).insert(ignore_permissions=True)
	return code


def make_bom(materials: list[tuple[str, float]]) -> str:
	"""A default BOM for PRODUCT, one unit of each material at the given cost."""
	for name in frappe.get_all("BOM", {"item": PRODUCT, "docstatus": 1}, pluck="name"):
		frappe.get_doc("BOM", name).cancel()
	bom = frappe.get_doc(
		{
			"doctype": "BOM",
			"item": PRODUCT,
			"company": COMPANY,
			"quantity": 1,
			"is_default": 1,
			"is_active": 1,
			"items": [{"item_code": code, "qty": 1} for code, _rate in materials],
		}
	).insert(ignore_permissions=True)
	bom.submit()
	# the material costs a BOM would take from valuation or a price list
	for row, (_code, rate) in zip(bom.items, materials, strict=True):
		frappe.db.set_value("BOM Item", row.name, {"rate": rate, "amount": rate})
	return bom.name


def make_certificate(agreement=UAE, **values):
	return frappe.get_doc(
		{
			"doctype": "Certificate of Origin",
			"certificate_type": "Preferential" if agreement else "Non-Preferential",
			"trade_agreement": agreement,
			"company": COMPANY,
			"customer": FOREIGN_CUSTOMER,
			"destination_country": "United Arab Emirates",
			"items": [{"item_code": PRODUCT, "qty": 10, "fob_value": 1000, "origin_criterion": "RVC"}],
			**values,
		}
	).insert()


class TestTradeAgreements(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		setup_exim_company()
		make_tariff_item(bcd=10, sws=10)
		make_exchange_rate("USD", export_rate=80, import_rate=82)
		make_item(PRODUCT, TARIFF_CODE)
		make_item("_Test EXIM Yarn from China", "52051100", "China")
		make_item("_Test EXIM Dye from UAE", "32041100", "United Arab Emirates")
		make_item("_Test EXIM Indian Thread", "52041100")

	def test_rvc_from_bom(self):
		make_bom(
			[
				("_Test EXIM Yarn from China", 30),
				("_Test EXIM Dye from UAE", 10),
				("_Test EXIM Indian Thread", 5),  # no country of origin: taken as Indian
			]
		)
		row = make_certificate().items[0]
		# 10 units x (30 + 10) of imported materials on an FOB of 1000
		self.assertEqual((row.non_originating_value, row.rvc_percent), (400, 60))
		self.assertIn("_Test EXIM Indian Thread", row.origin_note)

	def test_manual_values_are_kept(self):
		make_bom([("_Test EXIM Yarn from China", 70)])
		certificate = make_certificate()
		self.assertEqual(certificate.items[0].rvc_percent, 30)
		certificate.items[0].update({"manual_values": 1, "non_originating_value": 500})
		certificate.save()
		self.assertEqual(certificate.items[0].rvc_percent, 50)

	def test_no_bom_leaves_rvc_to_be_entered(self):
		make_item("_Test EXIM Traded Rice")
		certificate = make_certificate(
			items=[{"item_code": "_Test EXIM Traded Rice", "qty": 1, "fob_value": 100}]
		)
		self.assertEqual(certificate.items[0].rvc_percent, 0)
		self.assertIn("No default BOM", certificate.items[0].origin_note)

	def test_status_and_validity(self):
		certificate = make_certificate(issuing_agency="Export Inspection Council (EIC)")
		self.assertEqual(certificate.status, "Draft")
		certificate.update({"application_number": "COO123", "application_date": today()})
		certificate.save()
		self.assertEqual(certificate.status, "Applied")
		certificate.update({"certificate_number": "AE/2026/1", "certificate_date": today()})
		certificate.save()
		self.assertEqual(certificate.status, "Issued")
		self.assertEqual(getdate(certificate.valid_upto), getdate(add_months(today(), 12)))

	def test_non_preferential_certificate_has_no_agreement(self):
		certificate = make_certificate(None)
		self.assertFalse(certificate.trade_agreement)
		self.assertFalse(certificate.items[0].origin_criterion)

	def test_bill_of_entry_at_concessional_rate_with_duty_saved(self):
		bill_of_entry = make_bill_of_entry(
			make_import_invoice(qty=10, rate=100),
			exim_trade_agreement=UAE,
			exim_origin_country="United Arab Emirates",
			exim_coo_number="AE-COO-1",
			exim_coo_date=today(),
		)
		for item in bill_of_entry.items:
			item.update({"exim_manual_rates": 1, "exim_bcd_rate": 0, "exim_sws_rate": 10})
		bill_of_entry.save()
		item = bill_of_entry.items[0]
		self.assertEqual((item.assessable_value, item.customs_duty), (82000, 0))
		# standard duty: BCD 10% = 8200, SWS 10% of BCD = 820
		self.assertEqual(bill_of_entry.exim_fta_duty_saved, 9020)

		self.assertRaises(frappe.ValidationError, bill_of_entry.submit)
		bill_of_entry.reload()
		bill_of_entry.exim_carotar_confirmed = 1
		bill_of_entry.save()
		bill_of_entry.submit()

	def test_bill_of_entry_claim_is_checked(self):
		def claim(**values):
			return make_bill_of_entry(
				make_import_invoice(qty=1, rate=100),
				exim_trade_agreement=UAE,
				exim_coo_number="AE-COO-2",
				**values,
			).save()

		self.assertRaises(frappe.ValidationError, claim, exim_origin_country="India", exim_coo_date=today())
		# certificate older than its 12 months' validity
		self.assertRaises(
			frappe.ValidationError,
			claim,
			exim_origin_country="United Arab Emirates",
			exim_coo_date=add_months(today(), -13),
		)
