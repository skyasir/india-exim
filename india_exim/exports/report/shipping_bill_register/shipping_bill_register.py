# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters: dict | None = None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns() -> list[dict]:
	return [
		{
			"label": _("Shipping Bill"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Shipping Bill",
			"width": 140,
		},
		{"label": _("SB No."), "fieldname": "shipping_bill_number", "fieldtype": "Data", "width": 100},
		{"label": _("SB Date"), "fieldname": "shipping_bill_date", "fieldtype": "Date", "width": 100},
		{"label": _("LEO Date"), "fieldname": "leo_date", "fieldtype": "Date", "width": 100},
		{"label": _("Port"), "fieldname": "port_code", "fieldtype": "Data", "width": 80},
		{
			"label": _("Customer"),
			"fieldname": "customer",
			"fieldtype": "Link",
			"options": "Customer",
			"width": 180,
		},
		{
			"label": _("Destination"),
			"fieldname": "destination_country",
			"fieldtype": "Link",
			"options": "Country",
			"width": 120,
		},
		{"label": _("Export Type"), "fieldname": "export_type", "fieldtype": "Data", "width": 160},
		{
			"label": _("Currency"),
			"fieldname": "currency",
			"fieldtype": "Link",
			"options": "Currency",
			"width": 70,
		},
		{
			"label": _("Invoice Value"),
			"fieldname": "total_invoice_value",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},
		{
			"label": _("FOB Value"),
			"fieldname": "total_fob_value",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},
		{
			"label": _("Customs Rate"),
			"fieldname": "customs_exchange_rate",
			"fieldtype": "Float",
			"precision": 4,
			"width": 90,
		},
		{"label": _("FOB (INR)"), "fieldname": "total_fob_value_inr", "fieldtype": "Currency", "width": 130},
		{"label": _("Drawback"), "fieldname": "total_drawback", "fieldtype": "Currency", "width": 110},
		{"label": _("RoDTEP"), "fieldname": "total_rodtep", "fieldtype": "Currency", "width": 110},
		{"label": _("IGST Paid"), "fieldname": "total_igst", "fieldtype": "Currency", "width": 110},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
		{"label": _("Realisation"), "fieldname": "realisation_status", "fieldtype": "Data", "width": 120},
		{
			"label": _("Outstanding"),
			"fieldname": "outstanding_value",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},
	]


def get_data(filters) -> list[dict]:
	conditions = {"docstatus": 1, "company": filters.company}
	if filters.from_date and filters.to_date:
		conditions["shipping_bill_date"] = ("between", [filters.from_date, filters.to_date])
	for field in ("customer", "destination_country", "export_type", "port_code", "status"):
		if filters.get(field):
			conditions[field] = filters.get(field)

	return frappe.get_all(
		"Shipping Bill",
		filters=conditions,
		fields=[column["fieldname"] for column in get_columns()],
		order_by="shipping_bill_date, name",
	)
