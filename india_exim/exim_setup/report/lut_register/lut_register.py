# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

"""Letters of Undertaking (GST RFD-11) with their validity and the zero-rated exports made under
each, for the annual renewal and for the GST auditor."""

import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate, today


def execute(filters: dict | None = None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns() -> list[dict]:
	return [
		{
			"label": _("LUT"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Letter of Undertaking",
			"width": 220,
		},
		{"label": _("Fiscal Year"), "fieldname": "fiscal_year", "fieldtype": "Data", "width": 100},
		{"label": _("ARN"), "fieldname": "arn", "fieldtype": "Data", "width": 160},
		{"label": _("Filed On"), "fieldname": "filed_on", "fieldtype": "Date", "width": 100},
		{"label": _("Valid From"), "fieldname": "valid_from", "fieldtype": "Date", "width": 100},
		{"label": _("Valid Upto"), "fieldname": "valid_upto", "fieldtype": "Date", "width": 100},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 90},
		{"label": _("Days to Expiry"), "fieldname": "days_to_expiry", "fieldtype": "Int", "width": 110},
		{"label": _("Export Invoices"), "fieldname": "invoices", "fieldtype": "Int", "width": 110},
		{
			"label": _("Export Value (INR)"),
			"fieldname": "export_value",
			"fieldtype": "Currency",
			"width": 150,
		},
	]


def get_data(filters) -> list[dict]:
	conditions = {"docstatus": ("<", 2)}
	if filters.get("company"):
		conditions["company"] = filters.company
	rows = frappe.get_all(
		"Letter of Undertaking",
		filters=conditions,
		fields=["name", "fiscal_year", "arn", "filed_on", "valid_from", "valid_upto"],
		order_by="valid_from desc",
	)
	usage = {
		row.exim_lut: row
		for row in frappe.get_all(
			"Sales Invoice",
			filters={"docstatus": 1, "exim_lut": ("in", [row.name for row in rows] or [""])},
			fields=[
				"exim_lut",
				{"COUNT": "name", "as": "invoices"},
				{"SUM": "base_grand_total", "as": "export_value"},
			],
			group_by="exim_lut",
		)
	}
	as_on = getdate(today())
	for row in rows:
		if getdate(row.valid_from) > as_on:
			row.status = _("Upcoming")
		elif getdate(row.valid_upto) < as_on:
			row.status = _("Expired")
		else:
			row.status = _("Active")
			row.days_to_expiry = date_diff(row.valid_upto, as_on)
		used = usage.get(row.name) or {}
		row.invoices = used.get("invoices") or 0
		row.export_value = flt(used.get("export_value"))
	return rows
