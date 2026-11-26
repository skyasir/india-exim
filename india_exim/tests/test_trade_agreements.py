"""Trade agreements: rules of origin on Certificates of Origin, concessional duty on Bills of Entry."""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_months, getdate, today

from india_exim.tests.fixtures import (
	COMPANY,
	FOREIGN_CUSTOMER,
	FY_START,
	TARIFF_CODE,
	make_exchange_rate,
	make_import_invoice,
	make_tariff_item,
	setup_exim_company,
)
from india_exim.tests.test_imports_and_payments import make_bill_of_entry
from india_exim.trade_agreements.doctype.trade_agreement.trade_agreement import seed_trade_agreements
from india_exim.utils.rates import get_tariff_rate

UAE = "India-UAE CEPA"
SAFTA = "SAFTA"
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
	"""A default BOM for PRODUCT, one unit of each material at the given rate."""
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


def make_certificate(agreement=UAE, destination="United Arab Emirates", **values):
	return frappe.get_doc(
		{
			"doctype": "Certificate of Origin",
			"certificate_type": "Preferential" if agreement else "Non-Preferential",
			"trade_agreement": agreement,
			"company": COMPANY,
			"customer": FOREIGN_CUSTOMER,
			"destination_country": destination,
			"items": [{"item_code": PRODUCT, "qty": 10, "fob_value": 1000}],
			**values,
		}
	).insert()


class TestTradeAgreements(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		setup_exim_company()
		seed_trade_agreements()
		make_tariff_item(bcd=10, sws=10)
		make_exchange_rate("USD", export_rate=80, import_rate=82)
		tariff = frappe.get_doc("Customs Tariff Item", TARIFF_CODE)
		if not any(row.trade_agreement == UAE for row in tariff.rates):
			tariff.append(
				"rates",
				{"effective_from": FY_START, "bcd_rate": 0, "sws_rate": 10, "trade_agreement": UAE},
			)
			tariff.save(ignore_permissions=True)

		make_item(PRODUCT, TARIFF_CODE)
		make_item("_Test EXIM Yarn from China", "52051100", "China")
		make_item("_Test EXIM Dye from UAE", "32041100", "United Arab Emirates")
		make_item("_Test EXIM Indian Thread", "52041100")
		make_item("_Test EXIM Grey Fabric from China", "52081190", "China")

	def test_standard_rate_leaves_out_concessional_rates(self):
		self.assertEqual(get_tariff_rate(TARIFF_CODE, today()).bcd_rate, 10)
		self.assertEqual(get_tariff_rate(TARIFF_CODE, today(), UAE).bcd_rate, 0)

	def test_rvc_and_tariff_shift_from_bom(self):
		make_bom(
			[
				("_Test EXIM Yarn from China", 30),
				("_Test EXIM Dye from UAE", 10),  # a partner country: originating
				("_Test EXIM Indian Thread", 5),  # no country of origin: taken as Indian
			]
		)
		certificate = make_certificate()
		row = certificate.items[0]
		self.assertEqual((row.non_originating_value, row.rvc_percent), (300, 70))
		self.assertEqual(row.origin_criterion, "RVC + CTSH")
		self.assertTrue(row.qualifies)
		self.assertIn("_Test EXIM Indian Thread", row.origin_note)
		self.assertTrue(certificate.all_items_qualify)

	def test_material_in_the_same_heading_fails_change_in_tariff_heading(self):
		make_bom([("_Test EXIM Grey Fabric from China", 20)])
		# 5208 11 vs 5208 31: the sub-heading changes (CEPA) but the heading does not (SAFTA)
		self.assertTrue(make_certificate().items[0].qualifies)
		row = make_certificate(SAFTA, "Sri Lanka").items[0]
		self.assertEqual(row.rvc_percent, 80)
		self.assertFalse(row.qualifies)
		self.assertIn("CTH not met", row.origin_note)

	def test_low_rvc_does_not_qualify_and_manual_values_are_kept(self):
		make_bom([("_Test EXIM Yarn from China", 70)])
		row = make_certificate().items[0]
		self.assertEqual(row.rvc_percent, 30)
		self.assertFalse(row.qualifies)

		certificate = make_certificate()
		certificate.items[0].update({"manual_values": 1, "non_originating_value": 500})
		certificate.save()
		self.assertEqual((certificate.items[0].rvc_percent, certificate.items[0].qualifies), (50, 1))

	def test_destination_must_be_a_partner_country(self):
		self.assertRaises(frappe.ValidationError, make_certificate, UAE, "Japan")

	def test_status_and_validity(self):
		make_bom([("_Test EXIM Yarn from China", 30)])
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
		certificate = make_certificate(None, "Japan")
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
		bill_of_entry.save()
		item = bill_of_entry.items[0]
		self.assertEqual((item.assessable_value, item.exim_bcd_rate, item.customs_duty), (82000, 0, 0))
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

		# goods of a country outside the agreement
		self.assertRaises(frappe.ValidationError, claim, exim_origin_country="China", exim_coo_date=today())
		# certificate older than its 12 months' validity
		self.assertRaises(
			frappe.ValidationError,
			claim,
			exim_origin_country="United Arab Emirates",
			exim_coo_date=add_months(today(), -13),
		)
