"""Values for the India EXIM number cards that a plain Count / Sum card cannot express."""

import frappe
from frappe.utils import date_diff, flt, getdate

INCENTIVE_RECEIVABLES = (
	"exim_drawback_receivable_account",
	"exim_rodtep_receivable_account",
	"exim_rosctl_receivable_account",
)


def get_default_company() -> str | None:
	return frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
		"Global Defaults", "default_company"
	)


@frappe.whitelist()
def get_incentives_receivable() -> dict:
	"""Drawback, RoDTEP and RoSCTL booked but not yet received (ledger balance)."""
	company = get_default_company()
	accounts = [
		account
		for account in frappe.get_cached_value("Company", company, list(INCENTIVE_RECEIVABLES)) or ()
		if account
	]
	balance = 0.0
	if accounts:
		rows = frappe.get_all(
			"GL Entry",
			filters={"company": company, "account": ("in", accounts), "is_cancelled": 0},
			fields=["debit", "credit"],
		)
		balance = sum(flt(row.debit) - flt(row.credit) for row in rows)
	return {"value": balance, "fieldtype": "Currency"}


@frappe.whitelist()
def get_unclaimed_shipping_bills() -> int:
	"""Shipping bills past LEO with an incentive that is not on any claim yet."""
	from india_exim.export_incentives.doctype.export_incentive_claim.export_incentive_claim import (
		get_existing_claim,
	)

	shipping_bills = frappe.get_all(
		"Shipping Bill",
		filters={"company": get_default_company(), "docstatus": 1, "leo_date": ("is", "set")},
		fields=["name", "total_drawback", "total_rodtep"],
	)
	count = 0
	for row in shipping_bills:
		pending = (flt(row.total_drawback) and not get_existing_claim(row.name, "Duty Drawback")) or (
			flt(row.total_rodtep) and not get_existing_claim(row.name, "RoDTEP")
		)
		count += bool(pending)
	return count


@frappe.whitelist()
def get_days_to_lut_expiry() -> int:
	"""Days left on the Letter of Undertaking valid today; 0 when there is none."""
	valid_upto = frappe.db.get_value(
		"Letter of Undertaking",
		{
			"company": get_default_company(),
			"valid_from": ("<=", getdate()),
			"valid_upto": (">=", getdate()),
		},
		"valid_upto",
	)
	return max(date_diff(valid_upto, getdate()), 0) if valid_upto else 0
