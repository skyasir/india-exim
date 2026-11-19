# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

"""Checklist documents still open on active export shipments, by owner and due date."""

import frappe
from frappe import _
from frappe.utils import date_diff, getdate, today

OPEN_DOCUMENT_STATUSES = ("Pending", "Applied", "Discrepancy")
CLOSED_SHIPMENT_STATUSES = ("Delivered", "Closed", "Cancelled")


def execute(filters: dict | None = None):
	filters = frappe._dict(filters or {})
	data = get_data(filters)
	return get_columns(), data, None, None, get_summary(data)


def get_columns() -> list[dict]:
	return [
		{
			"label": _("Shipment"),
			"fieldname": "shipment",
			"fieldtype": "Link",
			"options": "Export Shipment",
			"width": 140,
		},
		{
			"label": _("Customer"),
			"fieldname": "customer",
			"fieldtype": "Link",
			"options": "Customer",
			"width": 170,
		},
		{
			"label": _("Destination"),
			"fieldname": "destination_country",
			"fieldtype": "Link",
			"options": "Country",
			"width": 110,
		},
		{"label": _("ETD"), "fieldname": "etd", "fieldtype": "Date", "width": 95},
		{
			"label": _("Document"),
			"fieldname": "document_type",
			"fieldtype": "Link",
			"options": "Trade Document Type",
			"width": 200,
		},
		{"label": _("Mandatory"), "fieldname": "mandatory", "fieldtype": "Check", "width": 80},
		{"label": _("Stage"), "fieldname": "stage", "fieldtype": "Data", "width": 100},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 100},
		{"label": _("Due Date"), "fieldname": "due_date", "fieldtype": "Date", "width": 95},
		{"label": _("Overdue (Days)"), "fieldname": "overdue_days", "fieldtype": "Int", "width": 110},
		{
			"label": _("Responsible"),
			"fieldname": "responsible",
			"fieldtype": "Link",
			"options": "User",
			"width": 160,
		},
		{"label": _("Issued By"), "fieldname": "issued_by", "fieldtype": "Data", "width": 120},
		{"label": _("Instructions"), "fieldname": "instructions", "fieldtype": "Data", "width": 220},
	]


def get_data(filters) -> list[dict]:
	shipment = frappe.qb.DocType("Export Shipment")
	document = frappe.qb.DocType("Shipment Document")
	query = (
		frappe.qb.from_(document)
		.join(shipment)
		.on((shipment.name == document.parent) & (document.parenttype == "Export Shipment"))
		.select(
			shipment.name.as_("shipment"),
			shipment.customer,
			shipment.destination_country,
			shipment.etd,
			document.document_type,
			document.mandatory,
			document.stage,
			document.status,
			document.due_date,
			document.responsible,
			document.issued_by,
			document.instructions,
		)
		.where(shipment.company == filters.company)
		.where(shipment.status.notin(CLOSED_SHIPMENT_STATUSES))
		.where(document.status.isin(OPEN_DOCUMENT_STATUSES))
		.orderby(document.due_date)
		.orderby(shipment.name)
		.orderby(document.idx)
	)
	if filters.responsible:
		query = query.where(document.responsible == filters.responsible)
	if filters.customer:
		query = query.where(shipment.customer == filters.customer)
	if filters.mandatory_only:
		query = query.where(document.mandatory == 1)

	as_on = getdate(today())
	data = []
	for row in query.run(as_dict=True):
		row.overdue_days = max(date_diff(as_on, row.due_date), 0) if row.due_date else 0
		if filters.overdue_only and not row.overdue_days:
			continue
		data.append(row)
	return data


def get_summary(data: list[dict]) -> list[dict]:
	overdue = sum(1 for row in data if row.overdue_days)
	return [
		{"label": _("Open Documents"), "value": len(data), "datatype": "Int", "indicator": "Orange"},
		{
			"label": _("Overdue"),
			"value": overdue,
			"datatype": "Int",
			"indicator": "Red" if overdue else "Green",
		},
		{
			"label": _("Shipments"),
			"value": len({row.shipment for row in data}),
			"datatype": "Int",
			"indicator": "Blue",
		},
	]
