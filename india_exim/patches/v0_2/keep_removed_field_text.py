"""Free-text fields nothing used are gone. What was typed in them is moved to the notes next to them
(the customer's document instructions, the supplier's details, the document row's remarks)."""

import frappe
from frappe.utils import escape_html

CUSTOMER = {
	"exim_notify_party": "Notify Party",
	"exim_consignee": "Consignee on Transport Document",
	"exim_originals_required": "Sets of Originals Required",
	"exim_preferred_courier": "Courier for Originals",
}


def execute():
	for row in get_rows("Customer", [*CUSTOMER, "exim_document_instructions"], CUSTOMER):
		lines = [
			f"<p>{label}: {escape_html(str(row[field]))}</p>"
			for field, label in CUSTOMER.items()
			if row.get(field)
		]
		text = (row.get("exim_document_instructions") or "") + "".join(lines)
		frappe.db.set_value("Customer", row.name, "exim_document_instructions", text, update_modified=False)

	append("Supplier", "exim_origin_documents", "supplier_details", "Documents Usually Supplied")
	append("Shipment Document", "courier_reference", "remarks", "Courier AWB")

	# the date of registration has no notes field beside it: kept as a comment
	for row in get_rows("AD Code Registration", ["registered_on"], ["registered_on"]):
		frappe.get_doc("AD Code Registration", row.name).add_comment(
			"Info", f"Registered On: {frappe.format(row.registered_on, {'fieldtype': 'Date'})}"
		)


def get_rows(doctype: str, fields: list[str], any_of) -> list:
	"""Rows with a value in one of the removed columns (Frappe keeps the column itself)."""
	columns = frappe.db.get_table_columns(doctype)
	fields = [field for field in fields if field in columns]
	any_of = [field for field in any_of if field in columns]
	if not any_of:
		return []
	table = frappe.qb.DocType(doctype)
	rows = frappe.qb.from_(table).select(table.name, *[table[field] for field in fields]).run(as_dict=True)
	return [row for row in rows if any(row.get(field) for field in any_of)]


def append(doctype: str, removed: str, notes: str, label: str) -> None:
	for row in get_rows(doctype, [removed, notes], [removed]):
		text = "\n".join(part for part in (row.get(notes), f"{label}: {row[removed]}") if part)
		frappe.db.set_value(doctype, row.name, notes, text, update_modified=False)
