import frappe
from frappe.tests import IntegrationTestCase, change_settings
from frappe.utils import add_months, getdate, today

from india_exim.export_incentives.doctype.export_incentive_claim.export_incentive_claim import (
	create_rodtep_scrip,
	get_unclaimed_shipping_bills,
	record_receipt,
)
from india_exim.export_incentives.doctype.rodtep_scrip.rodtep_scrip import utilise_scrip
from india_exim.tests.fixtures import (
	COMPANY,
	bank_account,
	make_exchange_rate,
	make_export_invoice,
	make_incentive_rate,
	make_lut,
	make_tariff_item,
	setup_exim_company,
)


def get_balance(account: str, voucher_no: str | None = None) -> float:
	filters = {"account": account, "is_cancelled": 0}
	if voucher_no:
		filters["voucher_no"] = voucher_no
	rows = frappe.get_all("GL Entry", filters=filters, fields=["debit", "credit"])
	return sum(row.debit - row.credit for row in rows)


class TestExportIncentives(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		setup_exim_company()
		make_tariff_item()
		make_exchange_rate("USD", export_rate=80, import_rate=82)
		make_lut()
		make_incentive_rate("RoDTEP", 1)  # 1% of 80,000 = 800 per bill
		make_incentive_rate("Duty Drawback", 2)  # 2% of 80,000 = 1,600 per bill
		cls.company = frappe.get_doc("Company", COMPANY)

	def make_leo_shipping_bill(self):
		from india_exim.exports.doctype.shipping_bill.shipping_bill import make_shipping_bill

		invoice = make_export_invoice(qty=10, rate=100)
		shipping_bill = make_shipping_bill(invoice.name)
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
		return shipping_bill

	def make_claim(self, scheme, shipping_bills, sanctioned=None):
		claim = frappe.get_doc(
			{
				"doctype": "Export Incentive Claim",
				"company": COMPANY,
				"scheme": scheme,
				"scroll_number": frappe.generate_hash(length=6),
				"scroll_date": today(),
				"items": [{"shipping_bill": sb.name} for sb in shipping_bills],
			}
		).insert()
		if sanctioned is not None:
			claim.items[0].sanctioned_amount = sanctioned
			claim.save()
		claim.submit()
		return claim

	@change_settings("India EXIM Settings", {"incentive_accrual_point": "On LEO"})
	def test_drawback_short_sanction_reverses_difference_and_receipt_clears_receivable(self):
		shipping_bill = self.make_leo_shipping_bill()
		self.assertEqual(shipping_bill.total_drawback, 1600)

		claim = self.make_claim("Duty Drawback", [shipping_bill], sanctioned=1500)
		self.assertEqual(claim.difference_amount, 100)
		self.assertTrue(claim.sanction_journal_entry)
		receivable = self.company.exim_drawback_receivable_account
		self.assertEqual(get_balance(receivable, claim.sanction_journal_entry), -100)

		record_receipt(claim.name, today(), 1500, bank_account())
		claim.reload()
		self.assertEqual(claim.status, "Received")
		self.assertEqual(claim.outstanding_amount, 0)
		self.assertEqual(
			get_balance(receivable, shipping_bill.accrual_journal_entry)
			+ get_balance(receivable, claim.sanction_journal_entry)
			+ get_balance(receivable, claim.receipts[0].journal_entry),
			0,
		)

	@change_settings("India EXIM Settings", {"incentive_accrual_point": "On LEO"})
	def test_shipping_bill_cannot_be_claimed_twice(self):
		shipping_bill = self.make_leo_shipping_bill()
		self.make_claim("RoDTEP", [shipping_bill])
		self.assertNotIn(
			shipping_bill.name,
			[row["shipping_bill"] for row in get_unclaimed_shipping_bills(COMPANY, "RoDTEP")],
		)
		self.assertRaises(frappe.ValidationError, self.make_claim, "RoDTEP", [shipping_bill])

	@change_settings("India EXIM Settings", {"incentive_accrual_point": "On LEO"})
	def test_rodtep_scrip_used_for_duty_and_sold_at_discount(self):
		shipping_bill = self.make_leo_shipping_bill()
		claim = self.make_claim("RoDTEP", [shipping_bill])
		self.assertFalse(claim.sanction_journal_entry)  # sanctioned = accrued, nothing to adjust

		scrip_name = create_rodtep_scrip(claim.name, frappe.generate_hash(length=8), today(), 800)
		scrip = frappe.get_doc("RoDTEP Scrip", scrip_name)
		claim.reload()
		self.assertEqual(claim.status, "Received")
		self.assertEqual(get_balance(self.company.exim_rodtep_scrip_account, scrip.journal_entry), 800)

		self.assertRaises(
			frappe.ValidationError,
			utilise_scrip,
			scrip.name,
			"Sale",
			today(),
			900,
			sale_value=850,
			bank_account=bank_account(),
		)

		journal_entry = utilise_scrip(
			scrip.name, "Sale", today(), 300, sale_value=291, bank_account=bank_account()
		)
		scrip.reload()
		self.assertEqual(scrip.balance_amount, 500)
		self.assertEqual(scrip.status, "Partly Used")
		self.assertEqual(get_balance(self.company.exim_scrip_sale_loss_account, journal_entry), 9)

	@change_settings("India EXIM Settings", {"incentive_accrual_point": "On LEO"})
	def test_rosctl_from_shipping_bill_to_scrip(self):
		frappe.db.savepoint("rosctl")
		self.addCleanup(frappe.clear_cache)
		self.addCleanup(frappe.db.rollback, save_point="rosctl")
		rate = make_incentive_rate("RoSCTL", 2)
		rate.update({"cap_per_unit": 100, "cap_uom": "Nos", "central_rate": 3, "central_cap_per_unit": 200})
		rate.save()
		shipping_bill = self.make_leo_shipping_bill()
		row = shipping_bill.items[0]
		# FOB 80,000 for 10: State 2% = 1,600 capped at 1,000; Central 3% = 2,400 capped at 2,000
		expected = min(80000 * 0.02, 100 * row.uqc_qty) + min(80000 * 0.03, 200 * row.uqc_qty)
		self.assertEqual(shipping_bill.total_rosctl, expected)
		self.assertEqual(shipping_bill.total_rodtep, 0)  # not both on the same goods
		self.assertEqual(
			get_balance(self.company.exim_rosctl_receivable_account, shipping_bill.accrual_journal_entry),
			expected,
		)

		claim = self.make_claim("RoSCTL", [shipping_bill])
		self.assertEqual(claim.total_expected, expected)
		self.assertRaisesRegex(
			frappe.ValidationError, "e-scrip", record_receipt, claim.name, today(), 10, bank_account()
		)
		create_rodtep_scrip(claim.name, frappe.generate_hash(length=8), today(), expected)
		claim.reload()
		self.assertEqual(claim.status, "Received")

	@change_settings("India EXIM Settings", {"incentive_accrual_point": "On LEO"})
	def test_scrip_pays_no_more_than_the_duty(self):
		from india_exim.export_incentives.doctype.rodtep_scrip.rodtep_scrip import get_duty_left
		from india_exim.tests.fixtures import make_import_invoice
		from india_exim.tests.test_imports_and_payments import make_bill_of_entry

		claim = self.make_claim("RoDTEP", [self.make_leo_shipping_bill()])
		scrip = create_rodtep_scrip(claim.name, frappe.generate_hash(length=8), today(), 800)
		bill_of_entry = make_bill_of_entry(make_import_invoice(qty=1, rate=50))
		bill_of_entry.save()
		bill_of_entry.submit()
		duty = get_duty_left(bill_of_entry.name)
		self.assertEqual(duty, 451)  # 50 x 82 = 4,100 at BCD 10% + SWS 10% of BCD
		pay = lambda amount: utilise_scrip(  # noqa: E731
			scrip, "Customs Duty", today(), amount, bill_of_entry=bill_of_entry.name
		)
		self.assertRaisesRegex(frappe.ValidationError, "customs duty is left", pay, duty + 1)
		pay(400)
		self.assertRaisesRegex(frappe.ValidationError, "customs duty is left", pay, 52)
		pay(51)
		self.assertEqual(get_duty_left(bill_of_entry.name), 0)
		self.assertEqual(
			frappe.db.get_value("RoDTEP Scrip", scrip, "valid_upto"), getdate(add_months(today(), 24))
		)

	@change_settings("India EXIM Settings", {"incentive_accrual_point": "On Scroll"})
	def test_on_scroll_books_full_sanction_as_income(self):
		shipping_bill = self.make_leo_shipping_bill()
		self.assertFalse(shipping_bill.accrual_journal_entry)
		claim = self.make_claim("Duty Drawback", [shipping_bill])
		self.assertEqual(
			get_balance(self.company.exim_drawback_income_account, claim.sanction_journal_entry), -1600
		)

	def test_gst_refund_claim_lifecycle(self):
		from india_exim.export_incentives.doctype.gst_refund_claim.gst_refund_claim import (
			record_refund_receipt,
		)

		claim = frappe.get_doc(
			{
				"doctype": "GST Refund Claim",
				"company": COMPANY,
				"refund_type": "IGST Paid on Exports",
				"from_date": today(),
				"to_date": today(),
				"arn": "AA240000000001X",
				"claimed_amount": 10000,
			}
		).insert()
		self.assertEqual(claim.credit_account, self.company.exim_igst_refund_receivable_account)
		claim.submit()
		self.assertEqual(claim.status, "Filed")

		claim.sanctioned_amount = 9000
		claim.sanction_date = today()
		claim.save()
		self.assertEqual(claim.rejected_amount, 1000)
		self.assertEqual(claim.status, "Sanctioned")

		self.assertRaises(
			frappe.ValidationError, record_refund_receipt, claim.name, today(), 9500, bank_account()
		)
		record_refund_receipt(claim.name, today(), 9000, bank_account())
		claim.reload()
		self.assertEqual(claim.status, "Received")

	@change_settings("India EXIM Settings", {"incentive_accrual_point": "On LEO"})
	def test_cancelling_receipt_entry_reopens_claim(self):
		shipping_bill = self.make_leo_shipping_bill()
		claim = self.make_claim("Duty Drawback", [shipping_bill])
		journal_entry = record_receipt(claim.name, today(), claim.total_sanctioned, bank_account())
		frappe.get_doc("Journal Entry", journal_entry).cancel()
		claim.reload()
		self.assertEqual(claim.status, "Sanctioned")
		self.assertEqual(claim.outstanding_amount, claim.total_sanctioned)
		claim.cancel()

	@change_settings("India EXIM Settings", {"incentive_accrual_point": "On LEO"})
	def test_unused_scrip_can_be_cancelled(self):
		shipping_bill = self.make_leo_shipping_bill()
		claim = self.make_claim("RoDTEP", [shipping_bill])
		scrip = frappe.get_doc(
			"RoDTEP Scrip", create_rodtep_scrip(claim.name, frappe.generate_hash(length=8), today(), 800)
		)
		scrip.cancel()
		claim.reload()
		self.assertEqual(claim.status, "Sanctioned")
		self.assertEqual(frappe.db.get_value("Journal Entry", scrip.journal_entry, "docstatus"), 2)

		# the same e-scrip number can be recorded again after a cancellation, but not twice while active
		again = create_rodtep_scrip(claim.name, scrip.scrip_number, today(), 800)
		self.assertNotEqual(again, scrip.name)
		self.assertRaises(
			frappe.ValidationError, create_rodtep_scrip, claim.name, scrip.scrip_number, today(), 1
		)

	@change_settings("India EXIM Settings", {"incentive_accrual_point": "On LEO"})
	def test_dashboard_cards(self):
		from india_exim.utils.dashboard import (
			get_days_to_lut_expiry,
			get_incentives_receivable,
			get_unclaimed_shipping_bills,
		)

		frappe.defaults.set_user_default("Company", COMPANY)
		before = get_unclaimed_shipping_bills()
		receivable_before = get_incentives_receivable()["value"]
		shipping_bill = self.make_leo_shipping_bill()
		self.assertEqual(get_unclaimed_shipping_bills(), before + 1)
		self.assertEqual(
			get_incentives_receivable()["value"], receivable_before + 2400
		)  # 1,600 DBK + 800 RoDTEP

		self.make_claim("Duty Drawback", [shipping_bill])
		self.assertEqual(get_unclaimed_shipping_bills(), before + 1)  # RoDTEP still unclaimed
		self.make_claim("RoDTEP", [shipping_bill])
		self.assertEqual(get_unclaimed_shipping_bills(), before)
		self.assertGreater(get_days_to_lut_expiry(), 0)
