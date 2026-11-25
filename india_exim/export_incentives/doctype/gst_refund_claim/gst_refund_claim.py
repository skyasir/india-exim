# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

from india_exim.export_incentives.accounting import make_journal_entry

IGST_REFUND = "IGST Paid on Exports"


class GSTRefundClaim(Document):
	def validate(self):
		if getdate(self.to_date) < getdate(self.from_date):
			frappe.throw(_("Tax Period To cannot be before Tax Period From."))
		if not self.credit_account and self.refund_type == IGST_REFUND:
			self.credit_account = frappe.get_cached_value(
				"Company", self.company, "exim_igst_refund_receivable_account"
			)
		if self.refund_type != IGST_REFUND:
			self.shipping_bills = []
		self.validate_amounts()
		self.set_status()

	def before_update_after_submit(self):
		self.validate_amounts()
		self.set_status()

	def on_submit(self):
		if not self.arn:
			frappe.throw(_("Enter the refund ARN before submitting."))
		self.set_status(update=True)

	def on_cancel(self):
		if self.receipts:
			frappe.throw(_("Refund receipts are recorded against this claim; it cannot be cancelled."))
		self.set_status(update=True)

	def validate_amounts(self):
		if flt(self.claimed_amount) <= 0:
			frappe.throw(_("Claimed amount must be greater than zero."))
		if flt(self.sanctioned_amount) < 0 or flt(self.sanctioned_amount) - flt(self.claimed_amount) > 0.005:
			frappe.throw(_("Sanctioned amount must be between zero and the claimed amount."))
		if self.sanction_date:
			self.rejected_amount = flt(self.claimed_amount) - flt(self.sanctioned_amount)
		self.received_amount = sum(flt(row.amount) for row in self.receipts)

	def set_status(self, update=False):
		if self.docstatus == 0:
			status = "Draft"
		elif self.docstatus == 2:
			status = "Cancelled"
		elif not self.sanction_date:
			status = "Filed"
		elif not flt(self.sanctioned_amount):
			status = "Rejected"
		elif flt(self.received_amount) and flt(self.sanctioned_amount) - flt(self.received_amount) > 0.005:
			status = "Partly Received"
		elif flt(self.received_amount):
			status = "Received"
		else:
			status = "Sanctioned"

		if update:
			self.db_set("status", status)
		else:
			self.status = status


@frappe.whitelist()
def record_refund_receipt(claim: str, posting_date: str, amount: float, bank_account: str) -> str:
	doc = frappe.get_doc("GST Refund Claim", claim)
	doc.check_permission("submit")
	amount = flt(amount, 2)
	if doc.docstatus != 1 or not doc.sanction_date:
		frappe.throw(_("Record the sanction (amount and date) before the receipt."))
	if amount <= 0 or flt(doc.received_amount) + amount - flt(doc.sanctioned_amount) > 0.005:
		frappe.throw(_("Receipt cannot exceed the sanctioned amount still to be received."))

	journal_entry = make_journal_entry(
		doc.company,
		posting_date,
		[(bank_account, amount, 0), (doc.credit_account, 0, amount)],
		_("GST refund received against ARN {0}").format(doc.arn),
		doc.doctype,
		doc.name,
	)
	doc.append(
		"receipts",
		{
			"posting_date": posting_date,
			"amount": amount,
			"bank_account": bank_account,
			"journal_entry": journal_entry,
		},
	)
	doc.flags.ignore_validate_update_after_submit = True
	doc.save(ignore_permissions=True)
	return journal_entry


@frappe.whitelist()
def get_shipping_bills(company: str, from_date: str, to_date: str, claim: str | None = None) -> dict:
	"""Shipping bills with IGST paid, with LEO in the period and on no other refund claim."""
	frappe.has_permission("Shipping Bill", "read", throw=True)
	bills = frappe.get_list(
		"Shipping Bill",
		filters={
			"company": company,
			"docstatus": 1,
			"export_type": "With Payment of IGST",
			"total_igst": (">", 0),
			"leo_date": ("between", [from_date, to_date]),
		},
		fields=["name", "total_igst"],
		order_by="leo_date",
		limit=0,
	)
	claimed = set(
		frappe.get_all(
			"GST Refund Shipping Bill",
			filters={
				"shipping_bill": ("in", [row.name for row in bills] or [""]),
				"docstatus": ("<", 2),
				"parent": ("!=", claim or ""),
			},
			pluck="shipping_bill",
		)
	)
	bills = [row for row in bills if row.name not in claimed]
	return {"shipping_bills": [row.name for row in bills], "igst": sum(flt(row.total_igst) for row in bills)}
