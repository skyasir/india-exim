"""Default EXIM accounts kept on the Company master."""

import frappe
from frappe import _

ASSET_PARENTS = ("Loans and Advances (Assets)", "Current Assets")
INCOME_PARENTS = ("Direct Income", "Income")
EXPENSE_PARENTS = ("Indirect Expenses", "Expenses")
LIABILITY_PARENTS = ("Duties and Taxes", "Current Liabilities")

# Company fieldname -> account spec, grouped into the Export and Import sections of the EXIM tab.
# "reuse" lists standard chart-of-accounts heads used before anything new is created.
# Customs duty expense / payable are India Compliance's own Company fields and are not repeated here.
EXIM_ACCOUNTS = {
	"exim_drawback_receivable_account": {
		"label": "Duty Drawback Receivable",
		"section": "Export",
		"root_type": "Asset",
		"parents": ASSET_PARENTS,
	},
	"exim_rodtep_receivable_account": {
		"label": "RoDTEP Receivable",
		"section": "Export",
		"root_type": "Asset",
		"parents": ASSET_PARENTS,
	},
	"exim_rosctl_receivable_account": {
		"label": "RoSCTL Receivable",
		"section": "Export",
		"root_type": "Asset",
		"parents": ASSET_PARENTS,
	},
	"exim_rodtep_scrip_account": {
		"label": "RoDTEP Scrips in Hand",
		"section": "Export",
		"root_type": "Asset",
		"parents": ASSET_PARENTS,
	},
	"exim_igst_refund_receivable_account": {
		"label": "IGST Refund Receivable (Exports)",
		"section": "Export",
		"root_type": "Asset",
		"parents": ASSET_PARENTS,
	},
	"exim_drawback_income_account": {
		"label": "Duty Drawback Income",
		"section": "Export",
		"root_type": "Income",
		"parents": INCOME_PARENTS,
	},
	"exim_rodtep_income_account": {
		"label": "RoDTEP Income",
		"section": "Export",
		"root_type": "Income",
		"parents": INCOME_PARENTS,
	},
	"exim_rosctl_income_account": {
		"label": "RoSCTL Income",
		"section": "Export",
		"root_type": "Income",
		"parents": INCOME_PARENTS,
	},
	"exim_scrip_sale_loss_account": {
		"label": "Loss on Sale of Duty Credit Scrips",
		"section": "Export",
		"root_type": "Expense",
		"parents": EXPENSE_PARENTS,
	},
	"exim_incentive_recovery_account": {
		"label": "Export Incentive Recovery",
		"section": "Export",
		"root_type": "Expense",
		"parents": EXPENSE_PARENTS,
	},
	"exim_freight_outward_account": {
		"label": "Freight Outward",
		"section": "Export",
		"root_type": "Expense",
		"parents": EXPENSE_PARENTS,
		"reuse": ("Freight and Forwarding Charges",),
	},
	"exim_export_bank_charges_account": {
		"label": "Export Bank Charges",
		"section": "Export",
		"root_type": "Expense",
		"parents": EXPENSE_PARENTS,
		"reuse": ("Bank Charges",),
	},
	"exim_ecgc_premium_account": {
		"label": "ECGC Premium",
		"section": "Export",
		"root_type": "Expense",
		"parents": EXPENSE_PARENTS,
	},
	"exim_freight_inward_account": {
		"label": "Freight Inward",
		"section": "Import",
		"root_type": "Expense",
		"parents": EXPENSE_PARENTS,
		"account_type": "Expenses Included In Valuation",
		"reuse": ("Expenses Included In Valuation",),
	},
	"exim_clearing_charges_account": {
		"label": "CHA and Clearing Charges",
		"section": "Import",
		"root_type": "Expense",
		"parents": EXPENSE_PARENTS,
		"account_type": "Expenses Included In Valuation",
		"reuse": ("Expenses Included In Valuation",),
	},
	"exim_demurrage_account": {
		"label": "Detention and Demurrage",
		"section": "Import",
		"root_type": "Expense",
		"parents": EXPENSE_PARENTS,
	},
}


def setup_exim_accounts(company: str) -> None:
	"""Fill empty EXIM account fields, reusing standard heads and creating only what is missing."""
	company_doc = frappe.get_doc("Company", company)
	updates = {}
	for fieldname, spec in EXIM_ACCOUNTS.items():
		if company_doc.get(fieldname):
			continue
		account = get_or_create_account(company_doc, spec)
		if account:
			updates[fieldname] = account

	if not company_doc.get("exim_cost_center") and company_doc.cost_center:
		updates["exim_cost_center"] = company_doc.cost_center

	if updates:
		frappe.db.set_value("Company", company, updates)


def get_existing_account(company: str, spec: dict) -> str | None:
	for account_name in (*spec.get("reuse", ()), spec["label"]):
		account = frappe.db.get_value(
			"Account",
			{"company": company, "account_name": account_name, "is_group": 0, "disabled": 0},
		)
		if account:
			return account
	return None


def get_or_create_account(company_doc, spec: dict) -> str | None:
	existing = get_existing_account(company_doc.name, spec)
	if existing:
		return existing

	parent = get_parent_account(company_doc.name, spec["root_type"], spec["parents"])
	if not parent:
		return None

	account = frappe.get_doc(
		{
			"doctype": "Account",
			"account_name": spec["label"],
			"company": company_doc.name,
			"parent_account": parent,
			"account_type": spec.get("account_type", ""),
			"account_currency": company_doc.default_currency,
		}
	)
	account.flags.ignore_permissions = True
	account.insert()
	return account.name


def get_parent_account(company: str, root_type: str, candidates: tuple[str, ...]) -> str | None:
	for account_name in candidates:
		parent = frappe.db.get_value(
			"Account",
			{"company": company, "account_name": account_name, "is_group": 1, "root_type": root_type},
		)
		if parent:
			return parent

	return frappe.db.get_value(
		"Account",
		{"company": company, "is_group": 1, "root_type": root_type},
		order_by="lft desc",
	)


def get_exim_account(company: str, fieldname: str) -> str:
	"""Account from the Company EXIM tab; fails loudly when it is not set."""
	account = frappe.get_cached_value("Company", company, fieldname)
	if fieldname == "exim_forex_gain_loss_account" and not account:
		account = frappe.get_cached_value("Company", company, "exchange_gain_loss_account")

	if not account:
		label = EXIM_ACCOUNTS.get(fieldname, {}).get("label", fieldname)
		frappe.throw(
			_("Please set <b>{0}</b> in the EXIM tab of Company {1}.").format(_(label), frappe.bold(company)),
			title=_("EXIM Account Missing"),
		)
	return account
