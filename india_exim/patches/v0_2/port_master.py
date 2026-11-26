"""Ports are picked from the Port Master instead of being typed.

AD Code Registration is now the AD Codes table of each Indian port. Ports typed on documents become
Port Master records: an Indian customs port code is matched to the pre-loaded list; a port abroad is
matched by code or name, or created with what was typed as its code, to be renamed to its UN/LOCODE."""

import frappe
from frappe.utils import escape_html

from india_exim.exim_setup.doctype.port_master.port_master import (
	get_country_from_code,
	normalise_code,
	seed_ports,
)

# (doctype, port field, country field): ports in India, then ports abroad
INDIAN = [
	("Shipping Bill", "port_code", None),
	("Export Shipment", "port_of_loading", None),
	("Quotation", "exim_port_of_loading", None),
	("Sales Order", "exim_port_of_loading", None),
	("Import Shipment", "port_of_discharge", None),
	("Purchase Invoice", "exim_port_of_discharge", None),
]
FOREIGN = [
	("Export Shipment", "port_of_discharge", "destination_country"),
	("Quotation", "exim_port_of_discharge", "exim_destination_country"),
	("Sales Order", "exim_port_of_discharge", "exim_destination_country"),
	("Delivery Note", "exim_port_of_discharge", "exim_destination_country"),
	("Sales Invoice", "exim_port_of_discharge", "exim_destination_country"),
	("Import Shipment", "port_of_loading", "origin_country"),
	("Purchase Invoice", "exim_port_of_loading", "exim_origin_country"),
]


def execute():
	seed_ports()
	move_ad_codes()
	for doctype, field, country_field in INDIAN + FOREIGN:
		link_typed_ports(doctype, field, country_field)


def move_ad_codes():
	if not frappe.db.table_exists("AD Code Registration"):
		return
	table = frappe.qb.DocType("AD Code Registration")
	rows = frappe.qb.from_(table).select("*").orderby(table.creation).run(as_dict=True)
	for row in rows:
		port = get_port(row.port_code, "India")
		doc = frappe.get_doc("Port Master", port)
		if row.get("disabled"):
			doc.add_comment(
				"Info",
				escape_html(
					f"AD code {row.ad_code} of {row.company} ({row.bank or ''}) was disabled and is not carried over."
				),
			)
		elif not any(r.company == row.company and r.ad_code == row.ad_code for r in doc.ad_codes):
			doc.append(
				"ad_codes",
				{
					"company": row.company,
					"ad_code": row.ad_code,
					"bank": row.bank,
					"bank_account": row.bank_account,
					"port_address": row.port_address,
					"is_default": row.is_default
					and not any(r.company == row.company and r.is_default for r in doc.ad_codes),
				},
			)
			doc.flags.ignore_links = True
			doc.save(ignore_permissions=True)
		frappe.db.set_value(
			"Comment",
			{"reference_doctype": "AD Code Registration", "reference_name": row.name},
			{"reference_doctype": "Port Master", "reference_name": port},
			update_modified=False,
		)


def link_typed_ports(doctype: str, field: str, country_field: str | None) -> None:
	"""country_field is None for a port in India."""
	if not frappe.db.has_column(doctype, field):
		return
	fields = ["name", field]
	if country_field and frappe.db.has_column(doctype, country_field):
		fields.append(country_field)
	for row in frappe.get_all(doctype, filters={field: ("is", "set")}, fields=fields):
		country = row.get(country_field) if country_field else "India"
		port = get_port(row[field], country)
		if port != row[field]:
			frappe.db.set_value(doctype, row.name, field, port, update_modified=False)


def get_port(typed: str, country: str | None) -> str:
	"""The Port Master for what was typed, made when there is none."""
	code = normalise_code(typed)
	if frappe.db.exists("Port Master", code):
		return code
	name = typed.strip()
	by_name = frappe.db.get_value(
		"Port Master", {"port_name": name, **({"port_country": country} if country else {})}
	)
	if by_name:
		return by_name
	port = frappe.get_doc(
		{
			"doctype": "Port Master",
			"port_code": code,
			"port_name": name,
			"port_country": country or get_country_from_code(code),
		}
	)
	# kept as it was typed: the user sets the code, and the country when the document had none
	port.flags.ignore_validate = True
	port.insert(ignore_permissions=True)
	return port.name
