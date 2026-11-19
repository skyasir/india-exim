import frappe

from india_exim.setup.accounts import EXIM_ACCOUNTS, get_existing_account

# Accounts created by the first build that standard chart-of-accounts heads now replace.
SUPERSEDED = {
	"exim_freight_outward_account": "Freight Outward (Exports)",
	"exim_freight_inward_account": "Freight Inward (Imports)",
	"exim_clearing_charges_account": "CHA and Clearing Charges",
	"exim_export_bank_charges_account": "Export Bank Charges",
}


def execute():
	for company in frappe.get_all("Company", pluck="name"):
		for fieldname, old_label in SUPERSEDED.items():
			repoint(company, fieldname, old_label)
		delete_if_unused(company, "Customs Duty")


def repoint(company: str, fieldname: str, old_label: str) -> None:
	if not frappe.db.has_column("Company", fieldname):
		return
	current = frappe.db.get_value("Company", company, fieldname)
	if not current or frappe.db.get_value("Account", current, "account_name") != old_label:
		return

	spec = {**EXIM_ACCOUNTS[fieldname], "label": "__none__"}
	standard = get_existing_account(company, spec)
	if not standard:
		return
	frappe.db.set_value("Company", company, fieldname, standard)
	delete_if_unused(company, old_label)


def delete_if_unused(company: str, account_name: str) -> None:
	account = frappe.db.get_value(
		"Account", {"company": company, "account_name": account_name, "is_group": 0}
	)
	if not account or frappe.db.exists("GL Entry", {"account": account}):
		return
	if account in frappe.db.get_value(
		"Company", company, ["default_customs_expense_account", "default_customs_payable_account"]
	):
		return
	frappe.delete_doc("Account", account, ignore_permissions=True, force=True)
