# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

"""Advances received from overseas buyers that are not yet adjusted against an export invoice.

RBI's Master Direction on Export of Goods and Services: goods against an advance must be shipped
within the period RBI allows (India EXIM Settings), otherwise the AD bank reports it. The
advance is an ordinary Payment Entry; what is adjusted is read from ERPNext's Payment Ledger.
"""

import frappe
from frappe import _
from frappe.utils import add_months, date_diff, flt, getdate, today

DUE_SOON_DAYS = 60


def execute(filters: dict | None = None):
	filters = frappe._dict(filters or {})
	data = get_data(filters)
	return get_columns(), data, None, None, get_summary(data)


def get_columns() -> list[dict]:
	return [
		{
			"label": _("Payment Entry"),
			"fieldname": "payment_entry",
			"fieldtype": "Link",
			"options": "Payment Entry",
			"width": 150,
		},
		{"label": _("Received On"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{
			"label": _("Customer"),
			"fieldname": "customer",
			"fieldtype": "Link",
			"options": "Customer",
			"width": 180,
		},
		{"label": _("IRM / Reference"), "fieldname": "reference_no", "fieldtype": "Data", "width": 140},
		{"label": _("Sales Order"), "fieldname": "sales_orders", "fieldtype": "Data", "width": 150},
		{
			"label": _("Currency"),
			"fieldname": "currency",
			"fieldtype": "Link",
			"options": "Currency",
			"width": 70,
		},
		{
			"label": _("Advance"),
			"fieldname": "advance",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},
		{
			"label": _("Adjusted"),
			"fieldname": "adjusted",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},
		{
			"label": _("Unadjusted"),
			"fieldname": "unadjusted",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},
		{"label": _("Ship By"), "fieldname": "ship_by", "fieldtype": "Date", "width": 100},
		{"label": _("Days Left"), "fieldname": "days_left", "fieldtype": "Int", "width": 90},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
	]


def get_data(filters) -> list[dict]:
	as_on = getdate(filters.get("as_on_date") or today())
	months = frappe.db.get_single_value("India EXIM Settings", "export_advance_shipment_months") or 12
	conditions = {
		"docstatus": 1,
		"payment_type": "Receive",
		"party_type": "Customer",
		"posting_date": ("<=", as_on),
		"party": ("in", get_export_customers(filters.get("customer"))),
	}
	if filters.get("company"):
		conditions["company"] = filters.company
	payments = frappe.get_all(
		"Payment Entry",
		filters=conditions,
		fields=["name", "posting_date", "party", "reference_no", "paid_amount", "paid_from_account_currency"],
		order_by="posting_date, name",
	)
	if not payments:
		return []

	adjusted = get_adjusted_amounts([row.name for row in payments], as_on)
	orders = get_sales_orders([row.name for row in payments])
	data = []
	for row in payments:
		unadjusted = flt(row.paid_amount) - adjusted.get(row.name, 0)
		if unadjusted <= 0.01:
			continue
		ship_by = add_months(row.posting_date, months)
		days_left = date_diff(ship_by, as_on)
		status = _("Overdue") if days_left < 0 else _("Due Soon") if days_left <= DUE_SOON_DAYS else _("Open")
		if filters.get("overdue_only") and days_left >= 0:
			continue
		data.append(
			frappe._dict(
				payment_entry=row.name,
				posting_date=row.posting_date,
				customer=row.party,
				reference_no=row.reference_no,
				sales_orders=", ".join(orders.get(row.name, [])),
				currency=row.paid_from_account_currency,
				advance=flt(row.paid_amount),
				adjusted=flt(adjusted.get(row.name, 0), 2),
				unadjusted=flt(unadjusted, 2),
				ship_by=ship_by,
				days_left=days_left,
				status=status,
			)
		)
	return data


def get_export_customers(customer: str | None = None) -> list[str]:
	filters = {"exim_is_export": 1}
	if customer:
		filters["name"] = customer
	return frappe.get_all("Customer", filters=filters, pluck="name") or [""]


def get_adjusted_amounts(payment_entries: list[str], as_on) -> dict[str, float]:
	"""Amount of each payment entry allocated to sales invoices, in the party account currency."""
	ple = frappe.qb.DocType("Payment Ledger Entry")
	rows = (
		frappe.qb.from_(ple)
		.select(ple.voucher_no, ple.amount_in_account_currency)
		.where(ple.voucher_type == "Payment Entry")
		.where(ple.voucher_no.isin(payment_entries))
		.where(ple.against_voucher_type == "Sales Invoice")
		.where(ple.delinked == 0)
		.where(ple.posting_date <= as_on)
	).run(as_dict=True)
	adjusted = {}
	for row in rows:
		adjusted[row.voucher_no] = adjusted.get(row.voucher_no, 0) - flt(row.amount_in_account_currency)
	return adjusted


def get_sales_orders(payment_entries: list[str]) -> dict[str, list[str]]:
	rows = frappe.get_all(
		"Payment Entry Reference",
		filters={"parent": ("in", payment_entries), "reference_doctype": "Sales Order"},
		fields=["parent", "reference_name"],
	)
	orders = {}
	for row in rows:
		orders.setdefault(row.parent, []).append(row.reference_name)
	return orders


def get_summary(data: list[dict]) -> list[dict]:
	overdue = [row for row in data if row.days_left < 0]
	return [
		{"label": _("Open Advances"), "value": len(data), "datatype": "Int", "indicator": "Blue"},
		{
			"label": _("Due within {0} days").format(DUE_SOON_DAYS),
			"value": len([r for r in data if 0 <= r.days_left <= DUE_SOON_DAYS]),
			"datatype": "Int",
			"indicator": "Orange",
		},
		{
			"label": _("Overdue"),
			"value": len(overdue),
			"datatype": "Int",
			"indicator": "Red" if overdue else "Green",
		},
	]
