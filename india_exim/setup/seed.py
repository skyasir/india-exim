"""Standard master data shipped with India EXIM. Existing records are never overwritten."""

import json
from pathlib import Path

import frappe

DATA_DIR = Path(__file__).parent / "data"


# Trade Document Type -> the India EXIM print format that produces it
DOCUMENT_PRINT_FORMATS = {
	"Proforma Invoice": "Export Proforma Invoice",
	"Commercial Invoice": "Export Commercial Invoice",
	"Packing List": "Export Packing List",
	"Shipping Instructions": "Shipping Instructions",
	"VGM Declaration (SOLAS)": "VGM Declaration",
	"Bill of Exchange": "Bill of Exchange",
	"Bank Covering Letter / Export Bill Lodgement": "Bank Covering Letter",
	"Beneficiary Certificate": "Beneficiary Certificate",
}


def seed_master_data():
	from india_exim.exim_setup.doctype.port_master.port_master import seed_ports

	seed_ports()
	seed_trade_document_types()
	seed_country_groups()
	link_print_formats()


def link_print_formats():
	"""Point the standard document types at their print formats, unless a user chose another."""
	for document_type, print_format in DOCUMENT_PRINT_FORMATS.items():
		if not frappe.db.exists("Print Format", print_format):
			continue
		current = frappe.db.get_value("Trade Document Type", document_type, "print_format")
		if frappe.db.exists("Trade Document Type", document_type) and not current:
			frappe.db.set_value("Trade Document Type", document_type, "print_format", print_format)


def load(filename: str) -> list[dict]:
	return json.loads((DATA_DIR / filename).read_text())


def seed_trade_document_types():
	for row in load("trade_document_types.json"):
		if frappe.db.exists("Trade Document Type", row["document_name"]):
			continue
		frappe.get_doc({"doctype": "Trade Document Type", **row}).insert(ignore_permissions=True)


def seed_country_groups():
	known_countries = set(frappe.get_all("Country", pluck="name"))
	for row in load("country_groups.json"):
		if frappe.db.exists("Country Group", row["group_name"]):
			continue
		countries = [{"country": country} for country in row["countries"] if country in known_countries]
		frappe.get_doc(
			{
				"doctype": "Country Group",
				"group_name": row["group_name"],
				"description": row["description"],
				"countries": countries,
			}
		).insert(ignore_permissions=True)
