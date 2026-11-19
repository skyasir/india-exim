"""Reusable test fixtures. Rates here are illustrative only, never real notified rates."""

import frappe
from frappe.utils import add_days, getdate

COMPANY = "_Test Indian Registered Company"
FOREIGN_CUSTOMER = "_Test Foreign Customer"
TARIFF_CODE = "52083190"
ITEM_CODE = "_Test EXIM Cotton Fabric"
FY_START = getdate("2000-01-01")


def make_tariff_item(code: str = TARIFF_CODE, bcd: float = 10, sws: float = 10) -> str:
	if not frappe.db.exists("Customs Tariff Item", code):
		frappe.get_doc(
			{
				"doctype": "Customs Tariff Item",
				"tariff_code": code,
				"description": "Test tariff item",
				"rates": [
					{"effective_from": FY_START, "bcd_rate": bcd, "sws_rate": sws, "notification": "TEST"}
				],
			}
		).insert(ignore_permissions=True)
	return code


def make_incentive_rate(
	scheme: str, rate: float, cap: float = 0, tariff: str = TARIFF_CODE, effective_from=FY_START
):
	existing = frappe.db.get_value("Export Incentive Rate", {"scheme": scheme, "customs_tariff_item": tariff})
	if existing:
		frappe.delete_doc("Export Incentive Rate", existing, force=True)
	return frappe.get_doc(
		{
			"doctype": "Export Incentive Rate",
			"scheme": scheme,
			"customs_tariff_item": tariff,
			"rate": rate,
			"cap_per_unit": cap,
			"cap_uom": "Nos" if cap else None,
			"effective_from": effective_from,
			"notification": "TEST",
		}
	).insert(ignore_permissions=True)


def make_exchange_rate(currency: str = "USD", export_rate: float = 80, import_rate: float = 82, on=FY_START):
	name = f"{currency}-{getdate(on)}"
	if not frappe.db.exists("Customs Exchange Rate", name):
		frappe.get_doc(
			{
				"doctype": "Customs Exchange Rate",
				"currency": currency,
				"effective_from": on,
				"export_rate": export_rate,
				"import_rate": import_rate,
			}
		).insert(ignore_permissions=True)
	return name


def make_lut(company: str = COMPANY, valid_from=None, valid_upto=None) -> str:
	valid_from = valid_from or add_days(getdate(), -30)
	valid_upto = valid_upto or add_days(getdate(), 300)
	existing = frappe.db.get_value("Letter of Undertaking", {"company": company})
	if existing:
		return existing
	fiscal_year = frappe.get_all("Fiscal Year", pluck="name", limit=1)[0]
	return (
		frappe.get_doc(
			{
				"doctype": "Letter of Undertaking",
				"company": company,
				"fiscal_year": fiscal_year,
				"arn": "AD240000000001T",
				"filed_on": valid_from,
				"valid_from": valid_from,
				"valid_upto": valid_upto,
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


def make_export_item(code: str = ITEM_CODE) -> str:
	if not frappe.db.exists("Item", code):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": code,
				"item_group": "All Item Groups",
				"stock_uom": "Nos",
				"is_stock_item": 0,
				"gst_hsn_code": "52083190",
				"exim_customs_tariff_item": make_tariff_item(),
			}
		).insert(ignore_permissions=True)
	return code


def setup_exim_company(company: str = COMPANY) -> None:
	from india_exim.setup.accounts import setup_exim_accounts

	setup_exim_accounts(company)
	frappe.db.set_value("Company", company, "exim_iec", "AAQCA8719H")
	frappe.db.set_single_value("GST Settings", "enable_overseas_transactions", 1)
	frappe.clear_document_cache("Company", company)


def make_receivable_account(currency: str = "USD", company: str = COMPANY) -> str:
	abbr = frappe.get_cached_value("Company", company, "abbr")
	name = f"Debtors {currency} - {abbr}"
	if not frappe.db.exists("Account", name):
		parent = frappe.db.get_value(
			"Account", {"company": company, "account_type": "Receivable", "is_group": 1}
		) or frappe.db.get_value("Account", {"company": company, "account_name": "Accounts Receivable"})
		frappe.get_doc(
			{
				"doctype": "Account",
				"account_name": f"Debtors {currency}",
				"company": company,
				"parent_account": parent,
				"account_type": "Receivable",
				"account_currency": currency,
			}
		).insert(ignore_permissions=True)
	return name


def make_export_invoice(qty: float = 10, rate: float = 100, currency: str = "USD", **extra):
	from india_compliance.gst_india.utils.tests import create_sales_invoice

	make_export_item()
	return create_sales_invoice(
		customer=FOREIGN_CUSTOMER,
		currency=currency,
		conversion_rate=83,
		debit_to=make_receivable_account(currency),
		items=[{"item_code": ITEM_CODE, "qty": qty, "rate": rate, "gst_hsn_code": "52083190"}],
		**extra,
	)
