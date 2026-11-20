"""Carry a Sales Order's export details to its Delivery Notes and Sales Invoices.

ERPNext's mappers copy fields with the same name, so this only matters when a document was
made some other way: from a Delivery Note created before it had the Export Details tab, through
Get Items From, or by the API. Only empty fields are filled, so what the user typed wins.
"""

import frappe

ORDER_LINK = {"Delivery Note": "against_sales_order", "Sales Invoice": "sales_order"}
# fields that describe this document rather than the order
SKIP = {"exim_tab", "exim_summary", "exim_summary_section"}


def fill_from_sales_order(doc, method=None):
	if not doc.get("exim_is_export") or doc.docstatus != 0:
		return
	link = ORDER_LINK.get(doc.doctype)
	order = next((row.get(link) for row in doc.get("items") or [] if row.get(link)), None)
	if not order:
		return

	fields = [
		df.fieldname
		for df in frappe.get_meta("Sales Order").fields
		if df.fieldname.startswith("exim_")
		and df.fieldname not in SKIP
		and df.fieldtype not in frappe.model.no_value_fields
		and doc.meta.has_field(df.fieldname)
	]
	empty = [field for field in fields if not doc.get(field)]
	if not doc.get("port_code") and doc.meta.has_field("port_code"):
		empty.append("exim_port_of_loading")
	if not empty:
		return
	values = frappe.db.get_value("Sales Order", order, empty, as_dict=True) or {}
	for field, value in values.items():
		if not value:
			continue
		if field == "exim_port_of_loading":
			doc.port_code = value
		else:
			doc.set(field, value)
