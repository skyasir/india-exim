# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

from india_exim.export_incentives.accounting import make_journal_entry
from india_exim.setup.accounts import get_exim_account

# scheme -> (Shipping Bill total field or None, receivable account field, income account field)
SCHEME_HEADS = {
	"Duty Drawback": ("total_drawback", "exim_drawback_receivable_account", "exim_drawback_income_account"),
	"RoDTEP": ("total_rodtep", "exim_rodtep_receivable_account", "exim_rodtep_income_account"),
	"RoSCTL": ("total_rosctl", "exim_rosctl_receivable_account", "exim_rosctl_income_account"),
}


def get_accrual_point() -> str:
	return frappe.db.get_single_value("India EXIM Settings", "incentive_accrual_point") or "On LEO"


class ExportIncentiveClaim(Document):
	def validate(self):
		self.validate_shipping_bills()
		self.set_totals()
		self.set_status()

	def on_submit(self):
		if not self.scroll_number:
			frappe.throw(_("Enter the Scroll No. issued by Customs before submitting."))
		self.make_sanction_entry()
		self.set_status(update=True)

	def on_cancel(self):
		if self.receipts:
			frappe.throw(_("Cancel the receipts / scrips recorded against this claim first."))
		self.ignore_linked_doctypes = ("Journal Entry", "GL Entry", "Payment Ledger Entry")
		if self.sanction_journal_entry:
			journal_entry = frappe.get_doc("Journal Entry", self.sanction_journal_entry)
			journal_entry.flags.ignore_permissions = True
			journal_entry.cancel()
		self.set_status(update=True)

	@property
	def heads(self):
		return SCHEME_HEADS[self.scheme]

	def validate_shipping_bills(self):
		total_field = self.heads[0]
		seen = set()
		for row in self.items:
			if row.shipping_bill in seen:
				frappe.throw(
					_("Row {0}: Shipping Bill {1} is listed twice.").format(row.idx, row.shipping_bill)
				)
			seen.add(row.shipping_bill)

			details = frappe.db.get_value(
				"Shipping Bill",
				row.shipping_bill,
				["docstatus", "company", "leo_date", "accrual_journal_entry", total_field or "name"]
				+ ([REVERSED_FIELDS[self.scheme]] if self.scheme in REVERSED_FIELDS else []),
				as_dict=True,
			)
			if details.docstatus != 1 or details.company != self.company:
				frappe.throw(
					_("Row {0}: Shipping Bill {1} must be submitted and belong to {2}.").format(
						row.idx, row.shipping_bill, self.company
					)
				)
			if not details.leo_date:
				frappe.throw(
					_("Row {0}: Shipping Bill {1} has no LEO date yet.").format(row.idx, row.shipping_bill)
				)

			claimed_in = get_existing_claim(row.shipping_bill, self.scheme, exclude=self.name)
			if claimed_in:
				frappe.throw(
					_("Row {0}: Shipping Bill {1} is already claimed in {2}.").format(
						row.idx, row.shipping_bill, frappe.bold(claimed_in)
					)
				)

			row.expected_amount = (
				net_incentive(details, self.scheme) if total_field else flt(row.expected_amount)
			)
			if self.is_new() and not flt(row.sanctioned_amount):
				row.sanctioned_amount = row.expected_amount
			if flt(row.sanctioned_amount) < 0:
				frappe.throw(_("Row {0}: Sanctioned amount cannot be negative.").format(row.idx))

	def set_totals(self):
		self.total_expected = sum(flt(row.expected_amount) for row in self.items)
		self.total_sanctioned = sum(flt(row.sanctioned_amount) for row in self.items)
		self.difference_amount = self.total_expected - self.total_sanctioned
		self.total_received = sum(flt(row.amount) for row in self.receipts)
		self.outstanding_amount = self.total_sanctioned - self.total_received

	def set_status(self, update=False):
		if self.docstatus == 0:
			status = "Draft"
		elif self.docstatus == 2:
			status = "Cancelled"
		elif flt(self.total_received) and flt(self.outstanding_amount) > 0.005:
			status = "Partly Received"
		elif flt(self.total_received):
			status = "Received"
		else:
			status = "Sanctioned"

		if update:
			self.db_set("status", status)
		else:
			self.status = status

	def make_sanction_entry(self):
		"""Recognise or adjust income when Customs sanctions the claim (scroll)."""
		accrual_point = get_accrual_point()
		if accrual_point == "On Receipt":
			return

		receivable = get_exim_account(self.company, self.heads[1])
		income = get_exim_account(self.company, self.heads[2])
		adjustment = 0.0
		for row in self.items:
			accrued, is_opening = frappe.db.get_value(
				"Shipping Bill", row.shipping_bill, ["accrual_journal_entry", "is_opening"]
			)
			# opening shipping bills: the receivable came in with the opening balances
			booked = is_opening or (accrual_point == "On LEO" and accrued)
			already_booked = flt(row.expected_amount) if booked else 0
			adjustment += flt(row.sanctioned_amount) - already_booked

		adjustment = flt(adjustment, 2)
		if not adjustment:
			return

		rows = [(receivable, adjustment, 0), (income, 0, adjustment)]
		if adjustment < 0:
			rows = [(income, -adjustment, 0), (receivable, 0, -adjustment)]

		journal_entry = make_journal_entry(
			self.company,
			self.scroll_date or self.posting_date,
			rows,
			_("{0} sanctioned under scroll {1}").format(self.scheme, self.scroll_number),
			self.doctype,
			self.name,
		)
		self.db_set("sanction_journal_entry", journal_entry)

	def get_receipt_credit_account(self) -> str:
		"""Receipts settle the receivable, or go straight to income when booked on receipt."""
		field = self.heads[2] if get_accrual_point() == "On Receipt" else self.heads[1]
		return get_exim_account(self.company, field)

	def add_receipt(self, posting_date, amount, bank_account=None, rodtep_scrip=None, journal_entry=None):
		amount = flt(amount, 2)
		if amount <= 0:
			frappe.throw(_("Receipt amount must be greater than zero."))
		if amount - flt(self.outstanding_amount) > 0.005:
			frappe.throw(
				_("Receipt of {0} exceeds the outstanding amount of {1}.").format(
					frappe.format(amount, "Currency"), frappe.format(self.outstanding_amount, "Currency")
				)
			)
		self.append(
			"receipts",
			{
				"posting_date": posting_date,
				"amount": amount,
				"bank_account": bank_account,
				"rodtep_scrip": rodtep_scrip,
				"journal_entry": journal_entry,
			},
		)
		self.set_totals()
		self.flags.ignore_validate_update_after_submit = True
		self.save(ignore_permissions=True)
		self.set_status(update=True)


def get_existing_claim(shipping_bill: str, scheme: str, exclude: str | None = None) -> str | None:
	claim_item = frappe.qb.DocType("Export Incentive Claim Item")
	claim = frappe.qb.DocType("Export Incentive Claim")
	query = (
		frappe.qb.from_(claim_item)
		.join(claim)
		.on(claim.name == claim_item.parent)
		.select(claim.name)
		.where(claim_item.shipping_bill == shipping_bill)
		.where(claim.scheme == scheme)
		.where(claim.docstatus < 2)
	)
	if exclude:
		query = query.where(claim.name != exclude)
	result = query.limit(1).run()
	return result[0][0] if result else None


# incentive taken back for credit notes / write-offs (india_exim.export_incentives.accounting)
REVERSED_FIELDS = {
	"Duty Drawback": "drawback_reversed",
	"RoDTEP": "rodtep_reversed",
	"RoSCTL": "rosctl_reversed",
}
# credited as a transferable e-scrip in the ICEGATE ledger, not as cash
SCRIP_SCHEMES = ("RoDTEP", "RoSCTL")


def net_incentive(shipping_bill: dict, scheme: str) -> float:
	"""Accrued incentive on a shipping bill less what was reversed after shipment."""
	total_field = SCHEME_HEADS[scheme][0]
	return flt(
		flt(shipping_bill.get(total_field)) - flt(shipping_bill.get(REVERSED_FIELDS.get(scheme, ""))), 2
	)


@frappe.whitelist()
def get_unclaimed_shipping_bills(
	company: str, scheme: str, from_date: str | None = None, to_date: str | None = None
) -> list[dict]:
	frappe.has_permission("Shipping Bill", "read", throw=True)
	total_field = SCHEME_HEADS[scheme][0]
	filters = {"company": company, "docstatus": 1, "leo_date": ("is", "set")}
	if from_date and to_date:
		filters["leo_date"] = ("between", (getdate(from_date), getdate(to_date)))
	if total_field:
		filters[total_field] = (">", 0)

	shipping_bills = frappe.get_all(
		"Shipping Bill",
		filters=filters,
		fields=[
			"name",
			"shipping_bill_number",
			"shipping_bill_date",
			"leo_date",
			total_field or "name as dummy",
			*([REVERSED_FIELDS[scheme]] if scheme in REVERSED_FIELDS else []),
		],
		order_by="leo_date",
	)
	return [
		{
			"shipping_bill": row.name,
			"shipping_bill_number": row.shipping_bill_number,
			"shipping_bill_date": row.shipping_bill_date,
			"leo_date": row.leo_date,
			"expected_amount": net_incentive(row, scheme) if total_field else 0,
		}
		for row in shipping_bills
		if not get_existing_claim(row.name, scheme)
	]


@frappe.whitelist()
def record_receipt(claim: str, posting_date: str, amount: float, bank_account: str) -> str:
	"""Cash received for a Drawback claim."""
	doc = frappe.get_doc("Export Incentive Claim", claim)
	doc.check_permission("submit")
	if doc.docstatus != 1:
		frappe.throw(_("Submit the claim before recording receipts."))
	if doc.scheme in SCRIP_SCHEMES:
		frappe.throw(_("{0} is received as an e-scrip. Use Create e-Scrip instead.").format(doc.scheme))
	if frappe.db.get_value("Account", bank_account, "company") != doc.company:
		frappe.throw(_("Account {0} does not belong to {1}.").format(bank_account, doc.company))

	journal_entry = make_journal_entry(
		doc.company,
		posting_date,
		[(bank_account, flt(amount), 0), (doc.get_receipt_credit_account(), 0, flt(amount))],
		_("{0} received against scroll {1}").format(doc.scheme, doc.scroll_number),
		doc.doctype,
		doc.name,
	)
	doc.add_receipt(posting_date, amount, bank_account=bank_account, journal_entry=journal_entry)
	return journal_entry


@frappe.whitelist()
def create_rodtep_scrip(claim: str, scrip_number: str, scrip_date: str, face_value: float) -> str:
	"""Record the e-scrip generated on ICEGATE against a sanctioned RoDTEP or RoSCTL claim."""
	doc = frappe.get_doc("Export Incentive Claim", claim)
	doc.check_permission("submit")
	if doc.docstatus != 1 or doc.scheme not in SCRIP_SCHEMES:
		frappe.throw(_("Scrips can only be created from a submitted RoDTEP or RoSCTL claim."))

	scrip = frappe.get_doc(
		{
			"doctype": "RoDTEP Scrip",
			"company": doc.company,
			"scrip_number": scrip_number,
			"scrip_date": scrip_date,
			"face_value": flt(face_value),
			"export_incentive_claim": doc.name,
		}
	)
	scrip.flags.ignore_permissions = True
	scrip.insert()
	scrip.submit()
	return scrip.name
