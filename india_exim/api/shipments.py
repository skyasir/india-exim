"""Data for the Shipment Control Tower and Document Board pages.

The pages only display and move things; every change goes through the Export Shipment document
(its validation, checklist gate and permissions), so Desk forms and the boards always agree.
"""

import frappe
from frappe import _
from frappe.utils import get_datetime, getdate, now_datetime, today

from india_exim.trade_documents.checklist import DONE_STATUSES

OPEN_STAGES = ("Planned", "Booked", "Stuffed", "Customs Cleared", "Shipped", "Documents Sent")
CUTOFFS = (("cutoff_documents", "Documents"), ("cutoff_vgm", "VGM"), ("cutoff_gate_in", "Gate-in"))
BOARD_COLUMNS = {
	"Pending": ("Pending",),
	"Applied": ("Applied",),
	"Received": ("Received", "Checked"),
	"Sent": ("Sent", "Accepted"),
	"Discrepancy": ("Discrepancy",),
}


def shipment_filters(company: str | None, customer: str | None) -> dict:
	filters = {"status": ("in", OPEN_STAGES)}
	if company:
		filters["company"] = company
	if customer:
		filters["customer"] = customer
	return filters


@frappe.whitelist()
def get_control_tower(company: str | None = None, customer: str | None = None) -> dict:
	"""Open shipments by stage, with schedule, next cut-off, documents, customs and payment."""
	frappe.has_permission("Export Shipment", "read", throw=True)
	shipments = frappe.get_list(
		"Export Shipment",
		filters=shipment_filters(company, customer),
		fields=[
			"name",
			"customer",
			"customer_name",
			"destination_country",
			"status",
			"mode_of_transport",
			"etd",
			"eta",
			"readiness_percent",
			"vessel_voyage",
			"booking_number",
			"bl_number",
			*[field for field, _label in CUTOFFS],
		],
		order_by="etd asc",
		limit_page_length=500,
	)
	names = [row.name for row in shipments]
	documents = get_documents(names)
	bills = get_shipping_bills(names)
	now = now_datetime()
	for row in shipments:
		upcoming = sorted(
			(get_datetime(row[field]), label)
			for field, label in CUTOFFS
			if row.get(field) and get_datetime(row[field]) >= now
		)
		if upcoming:
			row.next_cutoff = {
				"label": _(upcoming[0][1]),
				"at": upcoming[0][0],
				"hours": int((upcoming[0][0] - now).total_seconds() // 3600),
			}
		row.pending_documents = [
			{
				"document_type": doc.document_type,
				"overdue": bool(doc.due_date and getdate(doc.due_date) < getdate(today())),
			}
			for doc in documents.get(row.name, [])
			if doc.mandatory and doc.status not in DONE_STATUSES
		]
		row.shipping_bills = bills.get(row.name, [])
	return {"stages": list(OPEN_STAGES), "shipments": shipments}


def get_documents(shipments: list[str]) -> dict[str, list]:
	if not shipments:
		return {}
	rows = frappe.get_all(
		"Shipment Document",
		filters={"parenttype": "Export Shipment", "parent": ("in", shipments)},
		fields=[
			"parent",
			"name",
			"document_type",
			"status",
			"mandatory",
			"due_date",
			"responsible",
			"document_number",
			"document_date",
			"attachment",
		],
		order_by="due_date asc, idx asc",
	)
	grouped = {}
	for row in rows:
		grouped.setdefault(row.parent, []).append(row)
	return grouped


def get_shipping_bills(shipments: list[str]) -> dict[str, list]:
	if not shipments:
		return {}
	rows = frappe.get_all(
		"Shipping Bill",
		filters={"export_shipment": ("in", shipments), "docstatus": 1},
		fields=["export_shipment", "name", "shipping_bill_number", "status", "realisation_status"],
	)
	grouped = {}
	for row in rows:
		grouped.setdefault(row.export_shipment, []).append(row)
	return grouped


@frappe.whitelist()
def get_document_board(
	company: str | None = None, customer: str | None = None, responsible: str | None = None
) -> dict:
	"""Checklist rows of open shipments in columns by status."""
	frappe.has_permission("Export Shipment", "read", throw=True)
	shipments = {
		row.name: row
		for row in frappe.get_list(
			"Export Shipment",
			filters=shipment_filters(company, customer),
			fields=["name", "customer_name", "destination_country", "etd"],
			limit_page_length=500,
		)
	}
	columns = {column: [] for column in BOARD_COLUMNS}
	status_to_column = {status: column for column, statuses in BOARD_COLUMNS.items() for status in statuses}
	for parent, rows in get_documents(list(shipments)).items():
		for row in rows:
			if responsible and row.responsible != responsible:
				continue
			column = status_to_column.get(row.status)
			if not column:
				continue  # Not Required
			shipment = shipments[parent]
			row.update(
				shipment=parent,
				customer_name=shipment.customer_name,
				destination_country=shipment.destination_country,
				overdue=bool(
					row.due_date
					and getdate(row.due_date) < getdate(today())
					and column in ("Pending", "Applied")
				),
			)
			columns[column].append(row)
	return {"columns": [{"status": status, "rows": rows} for status, rows in columns.items()]}


@frappe.whitelist(methods=["POST"])
def update_document(
	shipment: str,
	row: str,
	status: str | None = None,
	attachment: str | None = None,
	document_number: str | None = None,
	document_date: str | None = None,
) -> dict:
	"""Move a checklist row to another status or attach its file, through the shipment."""
	doc = frappe.get_doc("Export Shipment", shipment)
	doc.check_permission("write")
	target = next((item for item in doc.documents if item.name == row), None)
	if not target:
		frappe.throw(_("Document row {0} is not on shipment {1}.").format(row, shipment))
	if status:
		statuses = frappe.get_meta("Shipment Document").get_field("status").options.split("\n")
		if status not in statuses:
			frappe.throw(_("{0} is not a document status.").format(status))
		target.status = status
	if attachment:
		target.attachment = attachment
	if document_number:
		target.document_number = document_number
	if document_date:
		target.document_date = document_date
	doc.save()
	return {"readiness_percent": doc.readiness_percent}
