"""Functions available in India EXIM's print formats (hooks.py > jinja)."""

import frappe

from india_exim.utils.item_details import get_item_details, get_packing


def exim_item_packing(item_code: str | None, stock_qty: float) -> frappe._dict:
	return get_packing(item_code, stock_qty)


def exim_customs_description(item_code: str | None) -> str:
	return get_item_details(item_code).exim_customs_description or ""


def exim_port(code: str | None) -> str:
	"""Indian customs port as printed: its name with the code."""
	from india_compliance.gst_india.constants import PORT_CODES

	name = PORT_CODES.get((code or "").strip().upper())
	return f"{name} ({code})" if name else code or ""


def exim_bank_lines(company: str, port_code: str | None = None) -> list[tuple[str, str]]:
	"""Bank details for remittance: the company's own printing lines when set, else the bank account
	of the port's AD code, else the company's default bank account."""
	printing = frappe.get_cached_doc("Company", company).get("bank_details_for_printing") or []
	lines = [(row.print_label, row.print_value) for row in printing if row.print_value]
	if lines:
		return lines

	ad = None
	if port_code:
		ad = frappe.db.get_value(
			"AD Code Registration",
			{"company": company, "port_code": port_code, "disabled": 0},
			["bank", "bank_account"],
			as_dict=True,
			order_by="is_default desc",
		)
	account = (ad and ad.bank_account) or frappe.db.get_value(
		"Bank Account", {"company": company, "is_company_account": 1, "is_default": 1, "disabled": 0}
	)
	details = (
		frappe.db.get_value(
			"Bank Account",
			account,
			["account_name", "bank", "bank_account_no", "iban", "branch_code"],
			as_dict=True,
		)
		if account
		else None
	) or frappe._dict()
	bank = details.bank or (ad and ad.bank)
	swift = frappe.db.get_value("Bank", bank, "swift_number") if bank else None
	return [
		(label, value)
		for label, value in (
			(frappe._("Bank"), bank),
			(frappe._("Account Name"), details.account_name),
			(frappe._("Account No."), details.bank_account_no),
			(frappe._("IBAN"), details.iban),
			(frappe._("Branch Code"), details.branch_code),
			(frappe._("SWIFT"), swift),
		)
		if value
	]
