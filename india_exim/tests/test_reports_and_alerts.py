import frappe
from frappe.desk.query_report import run
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, flt, getdate, today

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


def run_report(name: str, **filters) -> tuple[list[dict], list[dict]]:
	out = run(name, filters={"company": COMPANY, **filters})
	return [row for row in out["result"] if isinstance(row, dict)], out.get("report_summary") or []


class TestReportsAndAlerts(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		setup_exim_company()
		make_tariff_item()
		make_exchange_rate("USD", export_rate=80, import_rate=82)
		make_lut()
		make_incentive_rate("RoDTEP", 2, cap=5)
		make_incentive_rate("Duty Drawback", 1.5)

	def make_submitted_shipping_bill(self, **values):
		from india_exim.exports.doctype.shipping_bill.shipping_bill import make_shipping_bill

		invoice = make_export_invoice(qty=10, rate=100)
		shipping_bill = make_shipping_bill(invoice.name)
		shipping_bill.update(
			{
				"shipping_bill_number": frappe.generate_hash(length=7).upper(),
				"shipping_bill_date": today(),
				"port_code": "INNSA1",
				**values,
			}
		)
		shipping_bill.insert()
		shipping_bill.submit()
		return shipping_bill

	def test_open_shipping_bill_appears_in_register_and_ageing(self):
		shipping_bill = self.make_submitted_shipping_bill()

		register, _summary = run_report("Shipping Bill Register", from_date=today(), to_date=today())
		row = next(r for r in register if r["name"] == shipping_bill.name)
		self.assertEqual(flt(row["total_fob_value_inr"]), flt(shipping_bill.total_fob_value_inr))

		ageing, _summary = run_report("Export Realisation Ageing", as_on_date=today())
		row = next(r for r in ageing if r["name"] == shipping_bill.name)
		self.assertEqual(flt(row["outstanding_value"]), 1000)
		self.assertEqual(flt(row["outstanding_inr"]), 80000)
		self.assertEqual(row["bucket"], "0-90")
		self.assertEqual(row["overdue_days"], 0)

		overdue_only, _summary = run_report("Export Realisation Ageing", as_on_date=today(), overdue_only=1)
		self.assertNotIn(shipping_bill.name, [r["name"] for r in overdue_only])

		later = add_days(shipping_bill.realisation_due_date, 10)
		ageing, _summary = run_report("Export Realisation Ageing", as_on_date=later, overdue_only=1)
		row = next(r for r in ageing if r["name"] == shipping_bill.name)
		self.assertEqual(row["overdue_days"], 10)
		self.assertEqual(row["bucket"], "271-365")

	def test_incentive_register_shows_unclaimed_accrual(self):
		shipping_bill = self.make_submitted_shipping_bill(leo_date=today())
		rows, summary = run_report("Export Incentive Register", from_date=today(), to_date=today())
		mine = {r["scheme"]: r for r in rows if r["shipping_bill"] == shipping_bill.name}

		self.assertEqual(set(mine), {"Duty Drawback", "RoDTEP"})
		self.assertEqual(flt(mine["RoDTEP"]["accrued"]), flt(shipping_bill.total_rodtep))
		self.assertEqual(mine["RoDTEP"]["claim_status"], "Not Claimed")
		self.assertEqual(flt(mine["RoDTEP"]["receivable"]), flt(shipping_bill.total_rodtep))
		self.assertTrue(any(s["label"] == "Not Yet Claimed" and s["value"] > 0 for s in summary))

	def test_pending_trade_documents_lists_overdue_mandatory_rows(self):
		shipment = frappe.get_doc(
			{
				"doctype": "Export Shipment",
				"company": COMPANY,
				"customer": FOREIGN_CUSTOMER,
				"destination_country": "United States",
				"etd": add_days(getdate(), 5),
			}
		).insert()
		shipment.documents = []
		shipment.append(
			"documents",
			{
				"document_type": "Commercial Invoice",
				"mandatory": 1,
				"status": "Pending",
				"due_date": add_days(getdate(), -3),
			},
		)
		shipment.append(
			"documents",
			{"document_type": "Packing List", "mandatory": 1, "status": "Received", "due_date": today()},
		)
		shipment.save()

		rows, _summary = run_report("Pending Trade Documents", overdue_only=1)
		mine = [r for r in rows if r["shipment"] == shipment.name]
		self.assertEqual([r["document_type"] for r in mine], ["Commercial Invoice"])
		self.assertEqual(mine[0]["overdue_days"], 3)

	def test_realisation_due_notification_picks_shipping_bill(self):
		shipping_bill = self.make_submitted_shipping_bill()
		notification = frappe.get_doc("Notification", "Export Realisation Due")
		self.assertTrue(notification.is_standard)

		shipping_bill.db_set("realisation_due_date", add_days(today(), 30))
		due = [doc.name for doc in notification.get_documents_for_today()]
		self.assertIn(shipping_bill.name, due)

		shipping_bill.db_set("realisation_status", "Fully Realised")
		due = [doc.name for doc in notification.get_documents_for_today()]
		self.assertNotIn(shipping_bill.name, due)

	def test_unclaimed_incentive_notification_after_leo(self):
		shipping_bill = self.make_submitted_shipping_bill(
			shipping_bill_date=add_days(today(), -40), leo_date=add_days(today(), -30)
		)
		notification = frappe.get_doc("Notification", "Export Incentive Not Claimed")
		self.assertIn(shipping_bill.name, [doc.name for doc in notification.get_documents_for_today()])

	def test_lut_expiry_notification(self):
		lut = make_lut()
		valid_upto = frappe.db.get_value("Letter of Undertaking", lut, "valid_upto")
		frappe.db.set_value("Letter of Undertaking", lut, "valid_upto", add_days(today(), 30))
		try:
			notification = frappe.get_doc("Notification", "Letter of Undertaking Expiring")
			self.assertIn(lut, [doc.name for doc in notification.get_documents_for_today()])
		finally:
			frappe.db.set_value("Letter of Undertaking", lut, "valid_upto", valid_upto)
