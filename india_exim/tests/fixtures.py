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
	frappe.db.set_value("Customer", FOREIGN_CUSTOMER, "exim_is_export", 1)
	frappe.db.set_value("Supplier", "_Test Foreign Supplier", "exim_is_import", 1)
	frappe.clear_document_cache("Company", company)


def make_export_invoice(qty: float = 10, rate: float = 100, currency: str = "USD", **extra):
	from india_compliance.gst_india.utils.tests import create_sales_invoice

	make_export_item()
	return create_sales_invoice(
		customer=FOREIGN_CUSTOMER,
		currency=currency,
		conversion_rate=83,
		debit_to=make_party_account(currency, "Receivable"),
		items=[{"item_code": ITEM_CODE, "qty": qty, "rate": rate, "gst_hsn_code": "52083190"}],
		**extra,
	)


def make_party_account(
	currency: str = "USD", account_type: str = "Receivable", company: str = COMPANY
) -> str:
	abbr = frappe.get_cached_value("Company", company, "abbr")
	label = f"{'Debtors' if account_type == 'Receivable' else 'Creditors'} {currency}"
	name = f"{label} - {abbr}"
	if not frappe.db.exists("Account", name):
		parent = frappe.db.get_value(
			"Account", {"company": company, "account_type": account_type, "is_group": 1}
		)
		if not parent:
			parent = frappe.db.get_value(
				"Account", {"company": company, "account_type": account_type, "is_group": 0}, "parent_account"
			)
		frappe.get_doc(
			{
				"doctype": "Account",
				"account_name": label,
				"company": company,
				"parent_account": parent,
				"account_type": account_type,
				"account_currency": currency,
			}
		).insert(ignore_permissions=True)
	return name


def bank_account(company: str = COMPANY) -> str:
	abbr = frappe.get_cached_value("Company", company, "abbr")
	name = f"EXIM Test Bank - {abbr}"
	if not frappe.db.exists("Account", name):
		parent = frappe.db.get_value(
			"Account", {"company": company, "is_group": 1, "account_type": "Bank"}
		) or frappe.db.get_value(
			"Account", {"company": company, "is_group": 1, "account_name": "Current Assets"}
		)
		frappe.get_doc(
			{
				"doctype": "Account",
				"account_name": "EXIM Test Bank",
				"company": company,
				"parent_account": parent,
				"account_type": "Bank",
			}
		).insert(ignore_permissions=True)
	return name


def make_import_item(code: str = "_Test EXIM Import Yarn") -> str:
	if not frappe.db.exists("Item", code):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": code,
				"item_group": "All Item Groups",
				"stock_uom": "Nos",
				"is_stock_item": 1,
				"gst_hsn_code": "52083190",
				"exim_customs_tariff_item": make_tariff_item(),
			}
		).insert(ignore_permissions=True)
	return code


def make_import_invoice(qty: float = 10, rate: float = 100, currency: str = "USD"):
	from india_compliance.gst_india.utils.tests import create_purchase_invoice

	warehouse = frappe.db.get_value("Warehouse", {"company": COMPANY, "is_group": 0})
	return create_purchase_invoice(
		supplier="_Test Foreign Supplier",
		currency=currency,
		conversion_rate=83,
		credit_to=make_party_account(currency, "Payable"),
		update_stock=1,
		items=[
			{
				"item_code": make_import_item(),
				"qty": qty,
				"rate": rate,
				"warehouse": warehouse,
				"gst_hsn_code": "52083190",
			}
		],
	)


def make_payment(invoice, amount: float):
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	payment = get_payment_entry(
		invoice.doctype, invoice.name, party_amount=amount, bank_account=bank_account()
	)
	payment.reference_no = frappe.generate_hash(length=8)
	payment.reference_date = getdate()
	payment.insert()
	payment.submit()
	return payment
