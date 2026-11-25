# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_months, flt, getdate

from india_exim.export_incentives.accounting import make_journal_entry
from india_exim.setup.accounts import get_exim_account


class RoDTEPScrip(Document):
	def validate(self):
		if not self.export_incentive_claim:
			frappe.throw(_("Create e-scrips from a sanctioned RoDTEP or RoSCTL Export Incentive Claim."))
		if flt(self.face_value) <= 0:
			frappe.throw(_("Face value must be greater than zero."))
		duplicate = frappe.db.get_value(
			"RoDTEP Scrip",
			{"scrip_number": self.scrip_number, "docstatus": ("<", 2), "name": ("!=", self.name)},
		)
		if duplicate:
			frappe.throw(_("e-Scrip {0} is already recorded in {1}.").format(self.scrip_number, duplicate))
		if not self.valid_upto:
			months = frappe.db.get_single_value("India EXIM Settings", "scrip_validity_months") or 24
			self.valid_upto = add_months(self.scrip_date, months)
		if getdate(self.valid_upto) < getdate(self.scrip_date):
			frappe.throw(_("Valid Upto cannot be before the Scrip Date."))
		self.set_balance()
		self.set_status()

	def on_submit(self):
		claim = frappe.get_doc("Export Incentive Claim", self.export_incentive_claim)
		journal_entry = make_journal_entry(
			self.company,
			self.scrip_date,
			[
				(get_exim_account(self.company, "exim_rodtep_scrip_account"), self.face_value, 0),
				(claim.get_receipt_credit_account(), 0, self.face_value),
			],
			_("RoDTEP e-scrip {0} generated").format(self.scrip_number),
			self.doctype,
			self.name,
		)
		self.db_set("journal_entry", journal_entry)
		claim.add_receipt(
			self.scrip_date, self.face_value, rodtep_scrip=self.name, journal_entry=journal_entry
		)
		self.set_status(update=True)

	def on_cancel(self):
		if self.utilisations:
			frappe.throw(_("This scrip has already been used or sold and cannot be cancelled."))
		self.ignore_linked_doctypes = (
			"Journal Entry",
			"GL Entry",
			"Payment Ledger Entry",
			"Export Incentive Claim",
		)
		remove_claim_receipt(self)  # first, so the claim no longer links the entry being cancelled
		if self.journal_entry:
			journal_entry = frappe.get_doc("Journal Entry", self.journal_entry)
			journal_entry.flags.ignore_permissions = True
			journal_entry.cancel()
		self.set_status(update=True)

	def set_balance(self):
		self.utilised_amount = sum(flt(row.amount) for row in self.utilisations)
		self.balance_amount = flt(self.face_value) - self.utilised_amount

	def set_status(self, update=False):
		if self.docstatus == 0:
			status = "Draft"
		elif self.docstatus == 2:
			status = "Cancelled"
		elif self.balance_amount <= 0.005:
			status = "Fully Used"
		elif getdate(self.valid_upto) < getdate():
			status = "Expired"
		elif flt(self.utilised_amount):
			status = "Partly Used"
		else:
			status = "Active"

		if update:
			self.db_set("status", status)
		else:
			self.status = status

	def utilise(self, utilisation: dict) -> str:
		row = frappe._dict(utilisation)
		row.amount = flt(row.amount, 2)
		self.validate_utilisation(row)
		row.journal_entry = make_journal_entry(
			self.company,
			row.posting_date,
			self.get_utilisation_rows(row),
			_("RoDTEP scrip {0} used: {1}").format(self.scrip_number, row.utilisation_type),
			self.doctype,
			self.name,
		)
		self.append("utilisations", row)
		self.set_balance()
		self.flags.ignore_validate_update_after_submit = True
		self.save(ignore_permissions=True)
		self.set_status(update=True)
		return row.journal_entry

	def validate_utilisation(self, row):
		if self.docstatus != 1:
			frappe.throw(_("Submit the scrip before using it."))
		if row.amount <= 0 or row.amount - flt(self.balance_amount) > 0.005:
			frappe.throw(
				_("Amount must be between zero and the scrip balance of {0}.").format(
					frappe.format(self.balance_amount, "Currency")
				)
			)
		if getdate(row.posting_date) > getdate(self.valid_upto):
			frappe.throw(_("The scrip expired on {0}.").format(frappe.format(self.valid_upto, "Date")))
		if row.utilisation_type == "Customs Duty":
			if not row.bill_of_entry:
				frappe.throw(_("Select the Bill of Entry the duty is paid for."))
			details = frappe.db.get_value(
				"Bill of Entry", row.bill_of_entry, ["company", "docstatus"], as_dict=True
			)
			if not details or details.company != self.company or details.docstatus != 1:
				frappe.throw(_("Bill of Entry must be submitted and belong to {0}.").format(self.company))
			duty_left = get_duty_left(row.bill_of_entry)
			if row.amount - duty_left > 0.005:
				frappe.throw(
					_("Only {0} of customs duty is left to pay on Bill of Entry {1}.").format(
						frappe.format(duty_left, "Currency"), row.bill_of_entry
					)
				)
		elif not row.bank_account or flt(row.sale_value) <= 0:
			frappe.throw(_("Enter the sale consideration and the bank account it was received in."))
		elif flt(row.sale_value) - row.amount > 0.005:
			frappe.throw(_("Sale consideration cannot exceed the scrip value sold."))

	def get_utilisation_rows(self, row) -> list[tuple]:
		scrip_account = get_exim_account(self.company, "exim_rodtep_scrip_account")
		if row.utilisation_type == "Customs Duty":
			payable = frappe.db.get_value(
				"Bill of Entry", row.bill_of_entry, "customs_payable_account"
			) or frappe.get_cached_value("Company", self.company, "default_customs_payable_account")
			if not payable:
				frappe.throw(
					_("Set the Default Customs Payable Account on Company {0}.").format(self.company)
				)
			return [(payable, row.amount, 0), (scrip_account, 0, row.amount)]

		loss = flt(row.amount - flt(row.sale_value), 2)
		rows = [(row.bank_account, flt(row.sale_value), 0), (scrip_account, 0, row.amount)]
		if loss:
			rows.append((get_exim_account(self.company, "exim_scrip_sale_loss_account"), loss, 0))
		return rows


@frappe.whitelist()
def get_duty_left(bill_of_entry: str) -> float:
	"""Customs duty on a Bill of Entry not yet paid with scrips. IGST is not counted: a scrip pays
	customs duty only."""
	frappe.has_permission("Bill of Entry", "read", bill_of_entry, throw=True)
	duty = flt(frappe.db.get_value("Bill of Entry", bill_of_entry, "total_customs_duty"))
	paid = sum(
		flt(amount)
		for amount in frappe.get_all(
			"RoDTEP Scrip Utilisation",
			filters={"bill_of_entry": bill_of_entry, "docstatus": 1},
			pluck="amount",
		)
	)
	return max(flt(duty - paid, 2), 0.0)


def remove_claim_receipt(scrip) -> None:
	claim = frappe.get_doc("Export Incentive Claim", scrip.export_incentive_claim)
	claim.receipts = [row for row in claim.receipts if row.rodtep_scrip != scrip.name]
	claim.set_totals()
	claim.flags.ignore_validate_update_after_submit = True
	claim.flags.ignore_links = True
	claim.save(ignore_permissions=True)
	claim.set_status(update=True)


@frappe.whitelist()
def utilise_scrip(
	scrip: str,
	utilisation_type: str,
	posting_date: str,
	amount: float,
	bill_of_entry: str | None = None,
	sale_value: float | None = None,
	bank_account: str | None = None,
) -> str:
	doc = frappe.get_doc("RoDTEP Scrip", scrip)
	doc.check_permission("submit")
	return doc.utilise(
		{
			"utilisation_type": utilisation_type,
			"posting_date": posting_date,
			"amount": amount,
			"bill_of_entry": bill_of_entry,
			"sale_value": sale_value,
			"bank_account": bank_account,
		}
	)


def mark_expired_scrips() -> None:
	"""Daily: flag scrips whose validity has ended with a balance left."""
	for name in frappe.get_all(
		"RoDTEP Scrip",
		filters={"docstatus": 1, "status": ("in", ("Active", "Partly Used")), "valid_upto": ("<", getdate())},
		pluck="name",
	):
		frappe.db.set_value("RoDTEP Scrip", name, "status", "Expired")
