"""Credit notes and write-offs reversing incentives, agency commission, opening shipping bills,
merchant export, export advances, pre-shipment controls, export costing, print formats,
evidence packs and the boards."""

import io
import zipfile

import frappe
from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return
from frappe.desk.query_report import run
from frappe.tests import IntegrationTestCase, change_settings
from frappe.utils import add_days, add_months, getdate, today

from india_exim.tests.fixtures import (
	COMPANY,
	FOREIGN_CUSTOMER,
	TARIFF_CODE,
	bank_account,
	make_exchange_rate,
	make_export_invoice,
	make_export_item,
	make_incentive_rate,
	make_lut,
	make_party_account,
	make_payment,
	make_tariff_item,
	setup_exim_company,
)
from india_exim.utils import render_print_format

PRINT_FORMATS = {
	"Sales Invoice": [
		"Export Commercial Invoice",
		"Export Packing List",
		"Bill of Exchange",
		"Beneficiary Certificate",
	],
	"Shipping Bill": ["Bank Covering Letter"],
	"Export Shipment": ["Shipping Instructions", "VGM Declaration"],
}


def make_shipping_bill(invoice, leo=True, submit=True, **values):
	from india_exim.exports.doctype.shipping_bill.shipping_bill import make_shipping_bill as make

	shipping_bill = make(invoice.name)
	shipping_bill.update(
		{
			"shipping_bill_number": frappe.generate_hash(length=7).upper(),
			"shipping_bill_date": today(),
			"port_code": "INNSA1",
			**values,
		}
	)
	shipping_bill.insert()
	if submit:
		shipping_bill.submit()
	if leo:
		shipping_bill.leo_date = today()
		shipping_bill.save()
	return shipping_bill


def ledger_balance(account: str, reference: str) -> float:
	entries = frappe.get_all(
		"Journal Entry",
		filters={"exim_reference_name": reference, "docstatus": 1},
		pluck="name",
	)
	rows = frappe.get_all(
		"GL Entry",
		filters={"voucher_no": ("in", entries or [""]), "account": account, "is_cancelled": 0},
		fields=["debit", "credit"],
	)
	return sum(row.debit - row.credit for row in rows)


class TestPhaseOneCases(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		setup_exim_company()
		make_tariff_item()
		make_exchange_rate("USD", export_rate=80, import_rate=82)
		make_lut()
		make_incentive_rate("RoDTEP", 1)  # 1% of 80,000 = 800 per bill of 10 x 100 USD
		make_incentive_rate("Duty Drawback", 2)  # 2% of 80,000 = 1,600
		cls.company = frappe.get_doc("Company", COMPANY)

	@change_settings("India EXIM Settings", {"incentive_accrual_point": "On LEO"})
	def test_credit_note_after_shipment_reverses_incentives_in_proportion(self):
		invoice = make_export_invoice(qty=10, rate=100)
		shipping_bill = make_shipping_bill(invoice)
		self.assertEqual((shipping_bill.total_drawback, shipping_bill.total_rodtep), (1600, 800))

		credit_note = make_sales_return(invoice.name)
		credit_note.items[0].qty = -2  # 20% of the export value
		credit_note.insert()
		credit_note.submit()
		shipping_bill.reload()
		self.assertEqual((shipping_bill.drawback_reversed, shipping_bill.rodtep_reversed), (320, 160))
		receivable = self.company.exim_drawback_receivable_account
		self.assertEqual(ledger_balance(receivable, shipping_bill.name), 1280)
		self.assertEqual(
			ledger_balance(self.company.exim_incentive_recovery_account, shipping_bill.name), 480
		)

		# the incentive register and a new claim use the net amount
		rows, _summary = run_report("Export Incentive Register", from_date=today(), to_date=today())
		drawback = next(
			r for r in rows if r["shipping_bill"] == shipping_bill.name and r["scheme"] == "Duty Drawback"
		)
		self.assertEqual((drawback["accrued"], drawback["reversed"]), (1280, 320))

		credit_note.cancel()
		shipping_bill.reload()
		self.assertEqual((shipping_bill.drawback_reversed, shipping_bill.rodtep_reversed), (0, 0))
		self.assertEqual(ledger_balance(receivable, shipping_bill.name), 1600)

	@change_settings("India EXIM Settings", {"incentive_accrual_point": "On LEO"})
	def test_write_off_reverses_incentives_and_cancel_clears_everything(self):
		invoice = make_export_invoice(qty=10, rate=100)
		shipping_bill = make_shipping_bill(invoice)
		shipping_bill.append(
			"realisation_actions",
			{
				"action_type": "Write-off",
				"approved_by": "AD Bank",
				"approval_reference": "WO-1",
				"approval_date": today(),
				"write_off_value": 500,
			},
		)
		shipping_bill.save()
		shipping_bill.reload()
		self.assertEqual(shipping_bill.drawback_reversed, 800)
		self.assertEqual(shipping_bill.rodtep_reversed, 400)

		shipping_bill.cancel()
		self.assertFalse(
			frappe.db.exists("Journal Entry", {"exim_reference_name": shipping_bill.name, "docstatus": 1})
		)

	def test_agency_commission_is_not_counted_as_unrealised(self):
		invoice = make_export_invoice(qty=10, rate=100)
		shipping_bill = make_shipping_bill(invoice, leo=False, agency_commission=50)
		self.assertEqual(shipping_bill.outstanding_value, 950)
		make_payment(invoice, 950)
		shipping_bill.reload()
		self.assertEqual(shipping_bill.realisation_status, "Fully Realised")

	@change_settings("India EXIM Settings", {"incentive_accrual_point": "On LEO"})
	def test_opening_shipping_bill_posts_no_accrual_but_can_be_claimed(self):
		invoice = make_export_invoice(qty=10, rate=100)
		shipping_bill = make_shipping_bill(invoice, is_opening=1)
		self.assertFalse(shipping_bill.accrual_journal_entry)

		claim = frappe.get_doc(
			{
				"doctype": "Export Incentive Claim",
				"company": COMPANY,
				"scheme": "Duty Drawback",
				"scroll_number": frappe.generate_hash(length=6),
				"scroll_date": today(),
				"items": [{"shipping_bill": shipping_bill.name}],
			}
		).insert()
		claim.submit()
		self.assertEqual(claim.total_expected, 1600)
		# the receivable came with the opening balances, so the sanction books nothing more
		self.assertFalse(claim.sanction_journal_entry)

	def test_shipment_checklist_follows_the_shipping_bill(self):
		from india_exim.exports.doctype.export_shipment.export_shipment import (
			make_shipping_bill as from_shipment,
		)
		from india_exim.overrides.sales_invoice import make_export_shipment

		invoice = make_export_invoice(qty=10, rate=100)
		shipment = make_export_shipment(invoice.name)
		for document_type in (
			"Commercial Invoice",
			"Shipping Bill",
			"Let Export Order (LEO)",
			"Bill of Lading",
		):
			shipment.append(
				"documents", {"document_type": document_type, "mandatory": 1, "status": "Pending"}
			)
		shipment.insert()
		statuses = {row.document_type: row.status for row in shipment.documents}
		self.assertEqual(statuses["Commercial Invoice"], "Received")

		shipping_bill = from_shipment(shipment.name)
		shipping_bill.update(
			{
				"shipping_bill_number": frappe.generate_hash(length=7).upper(),
				"shipping_bill_date": today(),
				"port_code": "INNSA1",
			}
		)
		shipping_bill.insert()
		shipping_bill.submit()
		shipping_bill.leo_date = today()
		shipping_bill.save()

		shipment.reload()
		statuses = {row.document_type: row.status for row in shipment.documents}
		self.assertEqual(statuses["Shipping Bill"], "Received")
		self.assertEqual(statuses["Let Export Order (LEO)"], "Received")
		self.assertEqual(statuses["Bill of Lading"], "Pending")

		shipment.bl_number = "BL-TEST-1"
		shipment.bl_date = today()
		shipment.save()
		self.assertEqual(
			{r.document_type: r.status for r in shipment.documents}["Bill of Lading"], "Received"
		)

		shipping_bill.cancel()
		shipment.reload()
		self.assertEqual({r.document_type: r.status for r in shipment.documents}["Shipping Bill"], "Pending")

	def test_merchant_export_deadline_and_register(self):
		from india_compliance.gst_india.utils.tests import create_purchase_invoice

		purchase = create_purchase_invoice(
			supplier="_Test Registered Supplier",
			bill_no=frappe.generate_hash(length=6),
			bill_date=today(),
			exim_merchant_export=1,
			items=[{"item_code": make_export_item(), "qty": 10, "rate": 50}],
		)
		self.assertEqual(getdate(purchase.exim_merchant_export_due), getdate(add_days(today(), 90)))

		rows, _summary = run_report("Merchant Export Register")
		row = next(r for r in rows if r["name"] == purchase.name)
		self.assertEqual(row["status"], "Awaiting Export")

	def test_export_advance_register(self):
		payment = frappe.get_doc(
			{
				"doctype": "Payment Entry",
				"company": COMPANY,
				"payment_type": "Receive",
				"party_type": "Customer",
				"party": FOREIGN_CUSTOMER,
				"posting_date": today(),
				"paid_from": make_party_account("USD", "Receivable"),
				"paid_from_account_currency": "USD",
				"paid_to": bank_account(),
				"paid_to_account_currency": "INR",
				"paid_amount": 500,
				"source_exchange_rate": 80,
				"received_amount": 40000,
				"target_exchange_rate": 1,
				"reference_no": "IRM-ADV-1",
				"reference_date": today(),
			}
		).insert()
		payment.submit()

		rows, _summary = run_report("Export Advance Register")
		row = next(r for r in rows if r["payment_entry"] == payment.name)
		self.assertEqual(row["unadjusted"], 500)
		self.assertEqual(getdate(row["ship_by"]), getdate(add_months(payment.posting_date, 36)))

	def test_pre_shipment_controls(self):
		from india_exim.controls import validate

		order = frappe.get_doc(
			{
				"doctype": "Sales Order",
				"company": COMPANY,
				"customer": FOREIGN_CUSTOMER,
				"exim_is_export": 1,
				"exim_destination_country": "United States",
				"items": [{"item_code": make_export_item(), "qty": 1, "rate": 1}],
			}
		)
		order._action = "submit"
		frappe.db.set_value("Customer", FOREIGN_CUSTOMER, "exim_screened_on", today())
		try:
			frappe.db.set_value("Country", "United States", "exim_trade_risk", "Sanctioned")
			with change_settings("India EXIM Settings", {"pre_shipment_checks": "Block"}):
				self.assertRaisesRegex(frappe.ValidationError, "Sanctioned", validate, order)
				# end to end: a draft saves with a warning, the submit is stopped
				draft = frappe.copy_doc(order)
				draft.update(
					{"currency": "USD", "conversion_rate": 80, "delivery_date": add_days(today(), 5)}
				)
				draft.items[0].delivery_date = draft.delivery_date
				draft.insert()
				self.assertRaisesRegex(frappe.ValidationError, "Sanctioned", draft.submit)
			with change_settings("India EXIM Settings", {"pre_shipment_checks": "Warn"}):
				validate(order)  # only a message

			frappe.db.set_value("Country", "United States", "exim_trade_risk", None)
			frappe.db.set_value("Customs Tariff Item", TARIFF_CODE, "export_policy", "Prohibited")
			with change_settings("India EXIM Settings", {"pre_shipment_checks": "Block"}):
				self.assertRaisesRegex(frappe.ValidationError, "prohibited", validate, order)

			frappe.db.set_value("Customs Tariff Item", TARIFF_CODE, "export_policy", "Free")
			frappe.db.set_value("Customer", FOREIGN_CUSTOMER, "exim_screened_on", None)
			with change_settings(
				"India EXIM Settings", {"pre_shipment_checks": "Block", "buyer_screening_months": 12}
			):
				self.assertRaisesRegex(frappe.ValidationError, "not been screened", validate, order)
		finally:
			frappe.db.set_value("Country", "United States", "exim_trade_risk", None)
			frappe.db.set_value("Customs Tariff Item", TARIFF_CODE, "export_policy", "Free")
			frappe.db.set_value("Customer", FOREIGN_CUSTOMER, "exim_screened_on", today())

	def test_export_costing_sheet(self):
		sheet = frappe.get_doc(
			{
				"doctype": "Export Costing Sheet",
				"company": COMPANY,
				"customer": FOREIGN_CUSTOMER,
				"incoterm": "CIF",
				"currency": "USD",
				"exchange_rate": 80,
				"packing": 1000,
				"port_charges": 1000,
				"freight": 3000,
				"insurance": 500,
				"bank_charges_percent": 0,
				"margin_percent": 10,
				"include_incentives": 1,
				"items": [{"item_code": make_export_item(), "qty": 100, "ex_works_cost": 380}],
			}
		).insert()
		row = sheet.items[0]
		self.assertEqual((row.drawback_rate, row.rodtep_rate), (2, 1))
		self.assertEqual(sheet.total_fob_cost, 40000)
		self.assertEqual(sheet.total_cost_at_basis, 43500)
		# P x 0.9 + 3% x (P - 3,500) = 43,500  =>  P = 43,605 / 0.93
		self.assertAlmostEqual(sheet.total_price_inr, 46887.10, places=1)
		self.assertAlmostEqual(row.rate_fc, 5.8609, places=3)

	def test_print_formats_and_evidence_pack(self):
		from india_exim.overrides.sales_invoice import make_export_shipment
		from india_exim.utils.evidence_pack import build_evidence_pack

		invoice = make_export_invoice(qty=10, rate=100)
		shipment = make_export_shipment(invoice.name)
		shipment.append(
			"containers", {"container_number": "TEST1234567", "gross_weight": 1000, "vgm_weight": 3200}
		)
		shipment.insert()
		shipping_bill = make_shipping_bill(invoice, export_shipment=shipment.name)
		names = {
			"Sales Invoice": invoice.name,
			"Shipping Bill": shipping_bill.name,
			"Export Shipment": shipment.name,
		}
		for doctype, formats in PRINT_FORMATS.items():
			for print_format in formats:
				html = render_print_format(frappe.get_doc(doctype, names[doctype]), print_format)
				self.assertIn(COMPANY, html, print_format)
		self.assertIn(
			"LETTER OF UNDERTAKING",
			render_print_format(invoice, "Export Commercial Invoice"),
		)
		self.assertIn(
			"TEST1234567",
			render_print_format(frappe.get_doc("Export Shipment", shipment.name), "VGM Declaration"),
		)

		pack = zipfile.ZipFile(io.BytesIO(build_evidence_pack("Shipping Bill", shipping_bill.name)))
		index = pack.read("index.csv").decode()
		self.assertIn(invoice.name, index)
		self.assertIn(shipment.name, index)
		self.assertIn("audit_trail.csv", pack.namelist())

	def test_boards_and_new_reports(self):
		from india_exim.api.shipments import get_control_tower, get_document_board, update_document
		from india_exim.overrides.sales_invoice import make_export_shipment

		invoice = make_export_invoice(qty=10, rate=100)
		shipment = make_export_shipment(invoice.name)
		shipment.append(
			"documents", {"document_type": "Bill of Exchange", "mandatory": 1, "status": "Pending"}
		)
		shipment.insert()

		tower = get_control_tower(company=COMPANY)
		card = next(s for s in tower["shipments"] if s.name == shipment.name)
		self.assertIn("Bill of Exchange", [d["document_type"] for d in card.pending_documents])

		row = next(r for r in shipment.documents if r.document_type == "Bill of Exchange")
		update_document(shipment.name, row.name, status="Received")
		board = get_document_board(company=COMPANY)
		received = next(c for c in board["columns"] if c["status"] == "Received")
		self.assertIn(row.name, [r.name for r in received["rows"]])

		for name, filters in (
			("Shipment Tracker", {}),
			(
				"Export Summary",
				{"from_date": add_months(today(), -1), "to_date": today(), "group_by": "Customer"},
			),
			("LUT Register", {}),
			("Costing vs Actual", {}),
		):
			run_report(name, **filters)


def run_report(name: str, **filters):
	out = run(name, filters={"company": COMPANY, **filters})
	return [row for row in out["result"] if isinstance(row, dict)], out.get("report_summary") or []
