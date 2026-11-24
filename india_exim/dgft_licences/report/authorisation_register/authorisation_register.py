# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

"""Advance Authorisations and EPCG: imports and duty saved, export obligation and how much of it
is met, with the time left. For planning exports and for the EODC / redemption application."""

import frappe
from frappe import _
from frappe.utils import date_diff, getdate, today


def execute(filters: dict | None = None):
	filters = frappe._dict(filters or {})
	data = get_data(filters)
	return get_columns(), data, None, None, get_summary(data)


def get_columns() -> list[dict]:
	currency = {"fieldtype": "Currency", "width": 130}
	return [
		{
			"label": _("Authorisation"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Export Authorisation",
			"width": 140,
		},
		{"label": _("Scheme"), "fieldname": "scheme", "fieldtype": "Data", "width": 150},
		{
			"label": _("Authorisation No."),
			"fieldname": "authorisation_number",
			"fieldtype": "Data",
			"width": 130,
		},
		{"label": _("Date"), "fieldname": "authorisation_date", "fieldtype": "Date", "width": 100},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 110},
		{"label": _("CIF Allowed"), "fieldname": "total_cif_allowed", **currency},
		{"label": _("CIF Imported"), "fieldname": "total_cif_imported", **currency},
		{"label": _("Duty Saved"), "fieldname": "total_duty_saved", **currency},
		{"label": _("EO Required (FOB)"), "fieldname": "eo_required", **currency},
		{"label": _("EO Fulfilled"), "fieldname": "eo_fulfilled", **currency},
		{"label": _("EO %"), "fieldname": "eo_percent", "fieldtype": "Percent", "width": 80},
		{"label": _("EO Period Ends"), "fieldname": "eo_period_upto", "fieldtype": "Date", "width": 110},
		{"label": _("Days Left"), "fieldname": "days_left", "fieldtype": "Int", "width": 90},
		{"label": _("EODC"), "fieldname": "eodc_number", "fieldtype": "Data", "width": 110},
	]


def get_data(filters) -> list[dict]:
	conditions = {}
	for field in ("company", "scheme", "status"):
		if filters.get(field):
			conditions[field] = filters.get(field)
	if filters.get("open_only"):
		conditions["status"] = ("in", ("Active", "EO Period Over", "EO Fulfilled"))
	rows = frappe.get_all(
		"Export Authorisation",
		filters=conditions,
		fields=[column["fieldname"] for column in get_columns() if column["fieldname"] != "days_left"],
		order_by="eo_period_upto",
	)
	for row in rows:
		if row.eo_period_upto and row.status in ("Active", "EO Period Over"):
			row.days_left = date_diff(getdate(row.eo_period_upto), getdate(today()))
	return rows


def get_summary(data: list[dict]) -> list[dict]:
	active = [row for row in data if row.status == "Active"]
	due_soon = [row for row in active if row.get("days_left") is not None and row.days_left <= 90]
	over = [row for row in data if row.status == "EO Period Over"]
	return [
		{"label": _("Active"), "value": len(active), "datatype": "Int", "indicator": "Blue"},
		{
			"label": _("Duty Saved (Active)"),
			"value": sum(row.total_duty_saved or 0 for row in active),
			"datatype": "Currency",
			"indicator": "Green",
		},
		{"label": _("EO Due in 90 Days"), "value": len(due_soon), "datatype": "Int", "indicator": "Orange"},
		{
			"label": _("EO Period Over"),
			"value": len(over),
			"datatype": "Int",
			"indicator": "Red" if over else "Green",
		},
	]
