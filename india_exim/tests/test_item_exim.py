"""Item > Export & Import tab: kept once on the item, used by shipping bills, shipments and
the packing list."""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, getdate, today

from india_exim.tests.fixtures import (
	COMPANY,
	FOREIGN_CUSTOMER,
	FY_START,
	ITEM_CODE,
	TARIFF_CODE,
	make_exchange_rate,
	make_export_invoice,
	make_export_item,
	make_incentive_rate,
	make_lut,
	setup_exim_company,
)
from india_exim.utils import render_print_format

ITEM_VALUES = {
	"exim_uqc": "Kg",
	"exim_uqc_conversion_factor": 2.5,
	"weight_per_unit": 2.5,
	"weight_uom": "Kg",
	"exim_gross_weight_per_unit": 3,
	"exim_units_per_package": 4,
	"exim_package_type": "Carton",
	"exim_customs_description": "Woven cotton fabric, dyed, 200 g/m2",
	"exim_is_dangerous_goods": 1,
	"exim_un_number": "UN1993",
	"exim_imdg_class": "3 - Flammable Liquids",
}


class TestItemEximTab(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		setup_exim_company()
		make_exchange_rate("USD", export_rate=80, import_rate=82)
		make_lut()
		make_incentive_rate("RoDTEP", 1, cap=0.1).db_set("cap_uom", "Kg")  # per customs unit
		make_export_item()
		# the customs unit comes from the tariff item
		frappe.db.set_value("Customs Tariff Item", TARIFF_CODE, "uqc", "Kg")
		item = frappe.get_doc("Item", ITEM_CODE)
		item.update(ITEM_VALUES)
		item.save()

	@classmethod
	def tearDownClass(cls):
		item = frappe.get_doc("Item", ITEM_CODE)
		item.update({field: None for field in ITEM_VALUES})
		item.weight_per_unit = item.exim_uqc_conversion_factor = item.exim_gross_weight_per_unit = 0
		item.exim_units_per_package = item.exim_is_dangerous_goods = 0
		item.save()
		make_incentive_rate("RoDTEP", 1)
		frappe.db.delete(
			"Export Incentive Rate", {"scheme": "Duty Drawback", "customs_tariff_item": TARIFF_CODE}
		)
		make_incentive_rate("Duty Drawback", 2)
		super().tearDownClass()

	def test_item_validation(self):
		item = frappe.get_doc("Item", ITEM_CODE)
		item.exim_package_length, item.exim_package_width, item.exim_package_height = 50, 40, 30
		item.save()
		self.assertAlmostEqual(item.exim_package_volume, 0.06)

		item.exim_gross_weight_per_unit = 2
		self.assertRaisesRegex(frappe.ValidationError, "cannot be less than", item.save)

	def test_uqc_from_stock_unit(self):
		item = frappe.new_doc("Item")
		item.update({"stock_uom": "Kg", "exim_customs_tariff_item": TARIFF_CODE})  # UQC Kg
		from india_exim.overrides.item import set_uqc_conversion

		set_uqc_conversion(item)
		self.assertEqual(item.exim_uqc_conversion_factor, 1)

	def test_shipping_bill_quantity_in_customs_unit(self):
		from india_exim.exports.doctype.shipping_bill.shipping_bill import make_shipping_bill

		invoice = make_export_invoice(qty=10, rate=100)
		shipping_bill = make_shipping_bill(invoice.name)
		row = shipping_bill.items[0]
		self.assertEqual((row.uqc, row.uqc_qty), ("Kg", 25))

		# the per-unit cap works on the customs quantity: 0.1 x 25 kg, not 0.1 x 10 Nos
		shipping_bill.update(
			{
				"shipping_bill_number": frappe.generate_hash(length=7).upper(),
				"port_code": "INNSA1",
			}
		)
		shipping_bill.insert()
		self.assertEqual(shipping_bill.items[0].rodtep_amount, 2.5)

		# a quantity typed on the document is kept
		shipping_bill.items[0].uqc_qty = 30
		shipping_bill.save()
		self.assertEqual(shipping_bill.items[0].uqc_qty, 30)

	def test_shipment_takes_handling_and_packing_from_items(self):
		invoice = make_export_invoice(qty=10, rate=100)
		shipment = frappe.get_doc(
			{
				"doctype": "Export Shipment",
				"company": COMPANY,
				"customer": FOREIGN_CUSTOMER,
				"destination_country": "United States",
				"etd": add_days(getdate(), 20),
				"invoices": [{"sales_invoice": invoice.name}],
			}
		).insert()

		self.assertEqual((shipment.is_dangerous_goods, shipment.un_number), (1, "UN1993"))
		# no containers yet: estimated from the item, 10 units at 3 kg in cartons of 4
		self.assertEqual((shipment.total_gross_weight, shipment.total_packages), (30, 3))

		shipment.append("containers", {"container_number": "MSKU1234565", "packages": 5, "gross_weight": 40})
		shipment.save()
		self.assertEqual((shipment.total_gross_weight, shipment.total_packages), (40, 5))

	def test_packing_list_and_invoice_print(self):
		invoice = make_export_invoice(qty=10, rate=100)
		packing_list = render_print_format(invoice, "Export Packing List")
		self.assertIn("Woven cotton fabric, dyed", packing_list)
		self.assertIn("3 Carton", packing_list)
		self.assertIn("25", packing_list)  # net 10 x 2.5 kg
		self.assertIn("30", packing_list)  # gross 10 x 3 kg
		self.assertIn("Woven cotton fabric, dyed", render_print_format(invoice, "Export Commercial Invoice"))

	def test_tariff_summary(self):
		from india_exim.overrides.item import get_tariff_summary

		summary = get_tariff_summary(frappe.db.get_value("Item", ITEM_CODE, "exim_customs_tariff_item"))
		self.assertEqual(summary["duty"]["bcd_rate"], 10)
		self.assertEqual(summary["incentives"]["RoDTEP"]["rate"], 1)

	def test_rates_are_entered_on_the_item(self):
		frappe.db.savepoint("item_rates")
		self.addCleanup(frappe.clear_cache)
		self.addCleanup(frappe.db.rollback, save_point="item_rates")
		from india_exim.exports.doctype.shipping_bill.shipping_bill import make_shipping_bill
		from india_exim.utils.item_rates import add_duty_rate, add_incentive_rate, get_duty_rates
		from india_exim.utils.item_rates import get_incentive_rates as get_rates
		from india_exim.utils.rates import get_incentive_rate

		frappe.db.delete(
			"Export Incentive Rate", {"scheme": "Duty Drawback", "customs_tariff_item": TARIFF_CODE}
		)
		common = {"scheme": "Duty Drawback", "effective_from": add_days(today(), -5)}
		add_incentive_rate(TARIFF_CODE, {**common, "rate": 2})
		add_incentive_rate(TARIFF_CODE, {**common, "rate": 5, "item_code": ITEM_CODE, "only_this_item": 1})
		drawback = lambda item: sorted(  # noqa: E731
			row.rate for row in get_rates(TARIFF_CODE, item) if row.scheme == "Duty Drawback"
		)
		self.assertEqual(drawback(ITEM_CODE), [2, 5])
		self.assertEqual(drawback("Another Item"), [2])
		rate = lambda item=None: get_incentive_rate(  # noqa: E731
			"Duty Drawback", TARIFF_CODE, today(), item_code=item
		).rate
		self.assertEqual((rate(), rate("Another Item"), rate(ITEM_CODE)), (2, 2, 5))

		shipping_bill = make_shipping_bill(make_export_invoice(qty=10, rate=100).name)
		shipping_bill.update(
			{"shipping_bill_number": frappe.generate_hash(length=7).upper(), "port_code": "INNSA1"}
		)
		shipping_bill.insert()
		self.assertEqual(shipping_bill.items[0].drawback_rate, 5)

		# a brand rate is only for drawback, and for an item of that tariff code
		name = add_incentive_rate(
			TARIFF_CODE,
			{
				"scheme": "RoDTEP",
				"rate": 1.5,
				"effective_from": today(),
				"item_code": ITEM_CODE,
				"only_this_item": 1,
			},
		)
		self.assertFalse(frappe.db.get_value("Export Incentive Rate", name, "item_code"))

		# a new duty rate ends the one before it
		add_duty_rate(TARIFF_CODE, {"bcd_rate": 7.5, "sws_rate": 10, "effective_from": today()})
		self.assertEqual([row.bcd_rate for row in get_duty_rates(TARIFF_CODE)], [7.5])

	def test_item_picks_drawback_entry_and_claims(self):
		from india_exim.exports.doctype.shipping_bill.shipping_bill import make_shipping_bill

		frappe.db.delete(
			"Export Incentive Rate", {"scheme": "Duty Drawback", "customs_tariff_item": TARIFF_CODE}
		)
		for serial, rate in (("520801A", 2), ("520801B", 3)):
			frappe.get_doc(
				{
					"doctype": "Export Incentive Rate",
					"scheme": "Duty Drawback",
					"customs_tariff_item": TARIFF_CODE,
					"schedule_serial_no": serial,
					"rate": rate,
					"effective_from": FY_START,
					"notification": "TEST",
				}
			).insert()

		item = frappe.get_doc("Item", ITEM_CODE)
		item.exim_drawback_serial_no = "999999"
		self.assertRaisesRegex(frappe.ValidationError, "has no rate", item.save)
		item.reload()
		item.exim_drawback_serial_no = "520801B"
		item.exim_claim_rodtep = 0
		item.save()

		shipping_bill = make_shipping_bill(make_export_invoice(qty=10, rate=100).name)
		row = shipping_bill.items[0]
		self.assertEqual((row.drawback_serial_no, row.claim_rodtep), ("520801B", 0))
		shipping_bill.update(
			{"shipping_bill_number": frappe.generate_hash(length=7).upper(), "port_code": "INNSA1"}
		)
		shipping_bill.insert()
		row = shipping_bill.items[0]
		self.assertEqual((row.drawback_rate, row.drawback_amount, row.rodtep_amount), (3, 2400, 0))

		item.reload()
		item.exim_drawback_serial_no = None
		item.exim_claim_rodtep = 1
		item.save()
