# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

"""Bills of Entry whose import invoices are not fully paid (the RBI's IDPMS view).
Payment status is derived from the Payment Ledger by india_exim.fema.payments."""

import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate, today


def execute(filters: dict | None = None):
	filters = frappe._dict(filters or {})
	filters.as_on_date = getdate(filters.as_on_date or today())
	data = get_data(filters)
	return get_columns(), data, None, None, get_summary(data)


def get_columns() -> list[dict]:
	return [
		{
			"label": _("Bill of Entry"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Bill of Entry",
			"width": 140,
		},
		{"label": _("BE No."), "fieldname": "bill_of_entry_no", "fieldtype": "Data", "width": 100},
		{"label": _("BE Date"), "fieldname": "bill_of_entry_date", "fieldtype": "Date", "width": 100},
		{
			"label": _("Port"),
			"fieldname": "port_code",
			"fieldtype": "Link",
			"options": "Port Master",
			"width": 80,
		},
		{"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Data", "width": 180},
		{
			"label": _("Currency"),
			"fieldname": "exim_currency",
			"fieldtype": "Link",
			"options": "Currency",
			"width": 70,
		},
		{
			"label": _("Invoice Value"),
			"fieldname": "exim_invoice_value",
			"fieldtype": "Currency",
			"options": "exim_currency",
			"width": 120,
		},
		{
			"label": _("Paid"),
			"fieldname": "exim_paid_value",
			"fieldtype": "Currency",
			"options": "exim_currency",
			"width": 110,
		},
		{
			"label": _("Outstanding"),
			"fieldname": "outstanding",
			"fieldtype": "Currency",
			"options": "exim_currency",
			"width": 120,
		},
		{"label": _("Due Date"), "fieldname": "exim_payment_due_date", "fieldtype": "Date", "width": 100},
		{"label": _("Age (Days)"), "fieldname": "age", "fieldtype": "Int", "width": 90},
		{"label": _("Overdue (Days)"), "fieldname": "overdue_days", "fieldtype": "Int", "width": 110},
		{"label": _("Status"), "fieldname": "exim_payment_status", "fieldtype": "Data", "width": 100},
	]


def get_data(filters) -> list[dict]:
	rows = frappe.get_all(
		"Bill of Entry",
		filters={
			"docstatus": 1,
			"company": filters.company,
			"exim_payment_status": ("in", ("Unpaid", "Partly Paid")),
			"bill_of_entry_date": ("<=", filters.as_on_date),
		},
		fields=[
			"name",
			"bill_of_entry_no",
			"bill_of_entry_date",
			"port_code",
			"exim_currency",
			"exim_invoice_value",
			"exim_paid_value",
			"exim_payment_due_date",
			"exim_payment_status",
		],
		order_by="bill_of_entry_date, name",
	)
	suppliers = get_suppliers([row.name for row in rows])

	data = []
	for row in rows:
		row.supplier = ", ".join(sorted(suppliers.get(row.name, ())))
		if filters.supplier and filters.supplier not in suppliers.get(row.name, ()):
			continue
		row.outstanding = flt(row.exim_invoice_value) - flt(row.exim_paid_value)
		row.age = date_diff(filters.as_on_date, row.bill_of_entry_date)
		row.overdue_days = (
			max(date_diff(filters.as_on_date, row.exim_payment_due_date), 0)
			if row.exim_payment_due_date
			else 0
		)
		if filters.overdue_only and not row.overdue_days:
			continue
		data.append(row)
	return data


def get_suppliers(bills_of_entry: list[str]) -> dict[str, set]:
	if not bills_of_entry:
		return {}
	boe_item = frappe.qb.DocType("Bill of Entry Item")
	invoice = frappe.qb.DocType("Purchase Invoice")
	rows = (
		frappe.qb.from_(boe_item)
		.join(invoice)
		.on(invoice.name == boe_item.purchase_invoice)
		.select(boe_item.parent, invoice.supplier)
		.where(boe_item.parent.isin(bills_of_entry))
		.distinct()
	).run(as_dict=True)
	suppliers = {}
	for row in rows:
		suppliers.setdefault(row.parent, set()).add(row.supplier)
	return suppliers


def get_summary(data: list[dict]) -> list[dict]:
	overdue = [row for row in data if row.overdue_days]
	return [
		{"label": _("Bills of Entry Unpaid"), "value": len(data), "datatype": "Int", "indicator": "Orange"},
		{
			"label": _("Overdue"),
			"value": len(overdue),
			"datatype": "Int",
			"indicator": "Red" if overdue else "Green",
		},
	]
