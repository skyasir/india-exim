# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

"""Open export shipments on one screen: stage, schedule, next cut-off and document readiness."""

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime

CLOSED = ("Delivered", "Closed", "Cancelled")
CUTOFFS = (("cutoff_documents", "Documents"), ("cutoff_vgm", "VGM"), ("cutoff_gate_in", "Gate-in"))


def execute(filters: dict | None = None):
	filters = frappe._dict(filters or {})
	data = get_data(filters)
	return get_columns(), data, None, get_chart(data), get_summary(data)


def get_columns() -> list[dict]:
	return [
		{
			"label": _("Shipment"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Export Shipment",
			"width": 140,
		},
		{"label": _("Customer"), "fieldname": "customer_name", "fieldtype": "Data", "width": 170},
		{
			"label": _("Destination"),
			"fieldname": "destination_country",
			"fieldtype": "Link",
			"options": "Country",
			"width": 120,
		},
		{"label": _("Stage"), "fieldname": "status", "fieldtype": "Data", "width": 110},
		{"label": _("Mode"), "fieldname": "mode_of_transport", "fieldtype": "Data", "width": 80},
		{"label": _("Booking"), "fieldname": "booking_number", "fieldtype": "Data", "width": 120},
		{"label": _("Vessel / Voyage"), "fieldname": "vessel_voyage", "fieldtype": "Data", "width": 140},
		{"label": _("Next Cut-off"), "fieldname": "next_cutoff", "fieldtype": "Data", "width": 170},
		{"label": _("Hours Left"), "fieldname": "hours_left", "fieldtype": "Int", "width": 90},
		{"label": _("ETD"), "fieldname": "etd", "fieldtype": "Date", "width": 95},
		{"label": _("ETA"), "fieldname": "eta", "fieldtype": "Date", "width": 95},
		{
			"label": _("Documents Ready"),
			"fieldname": "readiness_percent",
			"fieldtype": "Percent",
			"width": 120,
		},
		{
			"label": _("Pending Documents"),
			"fieldname": "pending_documents",
			"fieldtype": "Data",
			"width": 260,
		},
		{"label": _("BL / AWB"), "fieldname": "bl_number", "fieldtype": "Data", "width": 120},
	]


def get_data(filters) -> list[dict]:
	conditions = {"status": ("not in", CLOSED)}
	for field in ("company", "customer", "destination_country", "status"):
		if filters.get(field):
			conditions[field] = filters.get(field)
	shipments = frappe.get_all(
		"Export Shipment",
		filters=conditions,
		fields=[
			"name",
			"customer_name",
			"destination_country",
			"status",
			"mode_of_transport",
			"booking_number",
			"vessel_voyage",
			"etd",
			"eta",
			"readiness_percent",
			"bl_number",
			*[field for field, _label in CUTOFFS],
		],
		order_by="etd, name",
	)
	pending = get_pending_documents([row.name for row in shipments])
	now = now_datetime()
	for row in shipments:
		row.pending_documents = ", ".join(pending.get(row.name, []))
		upcoming = sorted(
			(get_datetime(row[field]), label)
			for field, label in CUTOFFS
			if row.get(field) and get_datetime(row[field]) >= now
		)
		if upcoming:
			when, label = upcoming[0]
			row.next_cutoff = f"{label}: {frappe.format(when, {'fieldtype': 'Datetime'})}"
			row.hours_left = int((when - now).total_seconds() // 3600)
	if filters.get("cutoff_within_hours"):
		shipments = [
			row
			for row in shipments
			if row.get("hours_left") is not None and row.hours_left <= int(filters.cutoff_within_hours)
		]
	return shipments


def get_pending_documents(shipments: list[str]) -> dict[str, list[str]]:
	if not shipments:
		return {}
	rows = frappe.get_all(
		"Shipment Document",
		filters={
			"parenttype": "Export Shipment",
			"parent": ("in", shipments),
			"mandatory": 1,
			"status": ("in", ("Pending", "Applied", "Discrepancy")),
		},
		fields=["parent", "document_type"],
		order_by="due_date",
	)
	pending = {}
	for row in rows:
		pending.setdefault(row.parent, []).append(row.document_type)
	return pending


def get_chart(data: list[dict]) -> dict | None:
	if not data:
		return None
	stages = {}
	for row in data:
		stages[row.status] = stages.get(row.status, 0) + 1
	return {
		"data": {
			"labels": list(stages),
			"datasets": [{"name": _("Shipments"), "values": list(stages.values())}],
		},
		"type": "bar",
	}


def get_summary(data: list[dict]) -> list[dict]:
	urgent = [row for row in data if row.get("hours_left") is not None and row.hours_left <= 48]
	not_ready = [row for row in data if (row.readiness_percent or 0) < 100]
	return [
		{"label": _("Open Shipments"), "value": len(data), "datatype": "Int", "indicator": "Blue"},
		{
			"label": _("Cut-off within 48h"),
			"value": len(urgent),
			"datatype": "Int",
			"indicator": "Red" if urgent else "Green",
		},
		{
			"label": _("Documents Not Ready"),
			"value": len(not_ready),
			"datatype": "Int",
			"indicator": "Orange" if not_ready else "Green",
		},
	]
