"""India EXIM's tariff data: RoDTEP Appendix 4R loaded with dates, never over a user's own rates."""

import frappe
from frappe.tests import IntegrationTestCase

from india_exim.setup.tariff_data import PACKS, load_incentive_pack, load_tariff_data
from india_exim.utils.rates import get_incentive_rate


class TestTariffData(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		load_tariff_data()

	def test_rates_as_published(self):
		# figures checked against Appendix 4R w.e.f. 10.10.2024 and Notification 15/2026-27
		basmati = get_incentive_rate("RoDTEP", "10063020", "2025-06-01")
		self.assertEqual((basmati.rate, basmati.cap_per_unit), (0.9, 0))

		part = get_incentive_rate("RoDTEP", "87060029", "2025-06-01")
		self.assertEqual((part.rate, part.cap_per_unit, part.cap_uom), (0.8, 6500, "Nos"))

		logs = get_incentive_rate("RoDTEP", "44011110", "2025-06-01")
		self.assertEqual((logs.rate, logs.amount_per_unit, logs.cap_uom), (0, 400, "Tonne"))

		# split from 1 May 2026: the old line ends, the new lines start
		self.assertEqual(get_incentive_rate("RoDTEP", "03061900", "2026-04-30").cap_per_unit, 42)
		self.assertIsNone(get_incentive_rate("RoDTEP", "03061900", "2026-05-01"))
		self.assertIsNone(get_incentive_rate("RoDTEP", "03061910", "2026-04-30"))
		self.assertEqual(get_incentive_rate("RoDTEP", "03061910", "2026-05-01").rate, 3)

		# the scheme runs to the date it is notified for
		self.assertIsNone(get_incentive_rate("RoDTEP", "10063020", "2027-01-01"))

		tariff = frappe.db.get_value(
			"Customs Tariff Item", "44011110", ["uqc", "export_policy", "data_source"], as_dict=True
		)
		self.assertEqual((tariff.uqc, tariff.export_policy), ("Tonne", ""))  # policy not checked yet
		self.assertEqual(tariff.data_source, "RoDTEP Appendix 4R")

	def test_reload_is_idempotent_and_keeps_own_rates(self):
		before = frappe.db.count("Export Incentive Rate", {"scheme": "RoDTEP"})
		frappe.db.set_value(
			"Export Incentive Rate",
			{"scheme": "RoDTEP", "customs_tariff_item": "10063020", "data_source": "RoDTEP Appendix 4R"},
			"rate",
			5,
		)
		summary = load_incentive_pack(PACKS["rodtep_4r"])
		self.assertEqual((summary["rates_created"], summary["rates_updated"]), (0, 1))
		self.assertEqual(frappe.db.count("Export Incentive Rate", {"scheme": "RoDTEP"}), before)
		self.assertEqual(get_incentive_rate("RoDTEP", "10063020", "2025-06-01").rate, 0.9)

		# a rate entered by hand stays, and the pack's rate for that tariff is not added
		frappe.db.delete("Export Incentive Rate", {"scheme": "RoDTEP", "customs_tariff_item": "10063010"})
		frappe.get_doc(
			{
				"doctype": "Export Incentive Rate",
				"scheme": "RoDTEP",
				"customs_tariff_item": "10063010",
				"rate": 1.5,
				"effective_from": "2024-01-01",
			}
		).insert()
		summary = load_incentive_pack(PACKS["rodtep_4r"])
		self.assertGreaterEqual(summary["kept_own_rates"], 1)
		self.assertEqual(get_incentive_rate("RoDTEP", "10063010", "2025-06-01").rate, 1.5)

	def make_basmati_item(self):
		if not frappe.db.exists("GST HSN Code", "10063020"):
			frappe.get_doc(
				{"doctype": "GST HSN Code", "hsn_code": "10063020", "description": "Basmati rice"}
			).insert()
		if frappe.db.exists("Item", "_Test EXIM Basmati"):
			return frappe.get_doc("Item", "_Test EXIM Basmati")
		return frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": "_Test EXIM Basmati",
				"item_group": "All Item Groups",
				"stock_uom": "Kg",
				"is_stock_item": 0,
				"gst_hsn_code": "10063020",
			}
		).insert()

	def test_item_gets_tariff_from_hsn(self):
		item = self.make_basmati_item()
		self.assertEqual((item.exim_customs_tariff_item, item.exim_uqc), ("10063020", "Kg"))
		self.assertEqual(item.exim_uqc_conversion_factor, 1)

	def test_tariff_created_from_hsn_outside_the_pack(self):
		# chapter 63 (made-ups) is under RoSCTL, not RoDTEP, so the pack has no tariff item for it
		code = "63023100"
		frappe.db.delete("Customs Tariff Item", code)
		if not frappe.db.exists("GST HSN Code", code):
			frappe.get_doc(
				{"doctype": "GST HSN Code", "hsn_code": code, "description": "Bed linen of cotton"}
			).insert()
		item = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": "_Test EXIM Bedsheet",
				"item_group": "All Item Groups",
				"stock_uom": "Nos",
				"is_stock_item": 0,
				"gst_hsn_code": code,
			}
		).insert()
		self.assertEqual(item.exim_customs_tariff_item, code)
		tariff = frappe.get_doc("Customs Tariff Item", code)
		self.assertEqual((tariff.export_policy, tariff.data_source), ("", "GST HSN Code (India Compliance)"))

	def test_rate_entered_by_hand_is_compared_with_the_notified_rate(self):
		from india_exim.setup.tariff_data import differs_from_notified, use_notified_rates

		frappe.db.delete("Export Incentive Rate", {"scheme": "RoDTEP", "customs_tariff_item": "10063020"})
		own = frappe.get_doc(
			{
				"doctype": "Export Incentive Rate",
				"scheme": "RoDTEP",
				"customs_tariff_item": "10063020",
				"rate": 1.2,
				"effective_from": "2024-10-10",
			}
		).insert()
		self.assertEqual(differs_from_notified(own)["rate"], 0.9)

		use_notified_rates(own.name)
		self.assertFalse(frappe.db.exists("Export Incentive Rate", own.name))
		rate = get_incentive_rate("RoDTEP", "10063020", "2025-06-01")
		self.assertEqual((rate.rate, rate.data_source), (0.9, "RoDTEP Appendix 4R"))

	def test_item_fills_uqc_and_erpnext_tariff_number(self):
		item = self.make_basmati_item()
		item.exim_uqc = "Nos"  # read-only; always the tariff's unit
		item.save()
		self.assertEqual((item.exim_uqc, item.customs_tariff_number), ("Kg", "10063020"))

	def test_drawback_schedule_by_serial_number(self):
		from india_exim.utils.rates import get_incentive_rate, get_rosctl_rate, get_schedule_entries

		# two dated rates of one entry: 33/2024 raised cotton bed linen
		before = get_incentive_rate("Duty Drawback", "63023100", "2024-05-02", "630201")
		after = get_incentive_rate("Duty Drawback", "63023100", "2026-11-01", "630201")
		self.assertEqual((before.rate, before.cap_per_unit), (2.6, 40.5))
		self.assertEqual((after.rate, after.cap_per_unit, after.cap_uom), (3, 68.9, "Kg"))
		# several entries under the heading: nothing is guessed
		self.assertGreater(len(get_schedule_entries("Duty Drawback", "63023100", "2026-11-01")), 1)
		self.assertIsNone(get_incentive_rate("Duty Drawback", "63023100", "2026-11-01"))
		# a heading with one entry needs no choice
		self.assertEqual(get_incentive_rate("Duty Drawback", "52010020", "2026-11-01").rate, 0.5)
		# RoSCTL by the same serial number, State and Central
		rosctl = get_rosctl_rate("63012000", "2026-11-01", "630101")
		self.assertEqual(
			(rosctl.rate, rosctl.cap_per_unit, rosctl.central_rate, rosctl.central_cap_per_unit),
			(5, 40.8, 3.2, 26.1),
		)
		self.assertIsNone(get_rosctl_rate("63012000", "2027-01-01", "630101"))  # scheme not extended

	def test_cap_quantity_in_the_schedule_unit(self):
		from india_exim.utils.item_details import get_quantity_in

		code = frappe.generate_hash(length=8)
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": code,
				"item_group": "All Item Groups",
				"stock_uom": "Nos",
				"gst_hsn_code": "63023100",
				"weight_per_unit": 0.5,
				"weight_uom": "Kg",
			}
		).insert()
		self.assertEqual(get_quantity_in(code, "Nos", 10, "Kg", 5), 10)
		self.assertEqual(get_quantity_in(code, "Kg", 10, "Nos", 10), 5)
		self.assertIsNone(get_quantity_in(code, "Pair", 10, "Nos", 10))
