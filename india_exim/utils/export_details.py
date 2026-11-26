"""Carry a Sales Order's export details to its Delivery Notes and Sales Invoices.

ERPNext's mappers copy fields with the same name, so this only matters when a document was
made some other way: from a Delivery Note created before it had the Export Details tab, through
Get Items From, or by the API. Only empty fields are filled, so what the user typed wins.
"""

import frappe

from india_exim.exim_setup.doctype.port_master.port_master import get_ad_codes, get_only_port

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


def set_destination(doc, method=None):
	"""Destination from the buyer's address. Frappe fills a new document's Country link with the
	company's own country, which an export is never going to, so that counts as empty."""
	if not doc.get("exim_is_export") or doc.docstatus != 0:
		return
	home = frappe.get_cached_value("Company", doc.company, "country")
	if doc.exim_destination_country and doc.exim_destination_country != home:
		return
	address = doc.get("shipping_address_name") or doc.get("customer_address")
	country = frappe.db.get_value("Address", address, "country") if address else None
	if country and country != home:
		doc.exim_destination_country = country


def fill_from_last_invoice(doc, method=None):
	"""A repeat buyer's port, mode and terms, from their last export invoice. Only on a new document
	and only what is empty; the port is otherwise the one the company has an AD code at."""
	customer = doc.get("customer") or (
		doc.get("party_name") if doc.get("quotation_to") == "Customer" else None
	)
	if not doc.get("exim_is_export") or not doc.is_new() or doc.docstatus != 0:
		return
	last = (
		frappe.get_all(
			"Sales Invoice",
			filters={
				"customer": customer,
				"company": doc.company,
				"docstatus": 1,
				"is_return": 0,
				"exim_is_export": 1,
			},
			fields=[
				"port_code",
				"exim_destination_country",
				"exim_port_of_discharge",
				"exim_mode_of_transport",
				"exim_payment_terms_type",
			],
			order_by="posting_date desc, creation desc",
			limit=1,
		)
		if customer
		else []
	)
	values = last[0] if last else frappe._dict()
	if values.exim_payment_terms_type == "Letter of Credit":
		values.exim_payment_terms_type = None  # every LC is its own
	port_field = "port_code" if doc.meta.has_field("port_code") else "exim_port_of_loading"
	values[port_field] = values.pop("port_code", None) or get_only_port(doc.company)
	home = frappe.get_cached_value("Company", doc.company, "country")
	if doc.exim_destination_country == home and values.exim_destination_country:
		doc.exim_destination_country = None  # Frappe's own default, see set_destination
	for field, value in values.items():
		if value and doc.meta.has_field(field) and not doc.get(field):
			doc.set(field, value)


def set_port_address(doc, method=None):
	"""The port's address for the export e-Way Bill, from the AD code registered for the port."""
	if not doc.get("exim_is_export") or doc.docstatus != 0 or not doc.get("port_code"):
		return
	if doc.get("port_address") or not doc.meta.has_field("port_address"):
		return
	rows = get_ad_codes(doc.company, doc.port_code, ("port_address",))
	doc.port_address = next((row.port_address for row in rows if row.port_address), None)
