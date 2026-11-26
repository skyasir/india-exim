"""Write the JSON of India EXIM's standard print formats from their .html templates."""

import json
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "india_exim"
TS = "2026-11-26 14:00:00.000000"
FORMATS = {
	# name: (module folder, module, doc_type)
	"Export Proforma Invoice": ("exports", "Exports", "Sales Order"),
	"Export Commercial Invoice": ("exports", "Exports", "Sales Invoice"),
	"Export Packing List": ("exports", "Exports", "Sales Invoice"),
	"Bill of Exchange": ("exports", "Exports", "Sales Invoice"),
	"Beneficiary Certificate": ("exports", "Exports", "Sales Invoice"),
	"Bank Covering Letter": ("exports", "Exports", "Shipping Bill"),
	"Shipping Instructions": ("exports", "Exports", "Export Shipment"),
	"VGM Declaration": ("exports", "Exports", "Export Shipment"),
	"Import Clearing Instructions": ("imports", "Imports", "Purchase Invoice"),
}

for name, (folder, module, doc_type) in FORMATS.items():
	slug = name.lower().replace(" ", "_")
	path = APP / folder / "print_format" / slug
	(path / "__init__.py").touch()
	html = (path / f"{slug}.html").read_text()
	data = {
		"absolute_value": 0,
		"align_labels_right": 0,
		"creation": TS,
		"css": "",
		"custom_format": 1,
		"default_print_language": "en",
		"disabled": 0,
		"doc_type": doc_type,
		"docstatus": 0,
		"doctype": "Print Format",
		"font_size": 0,
		"html": html,
		"idx": 0,
		"line_breaks": 0,
		"margin_bottom": 10.0,
		"margin_left": 10.0,
		"margin_right": 10.0,
		"margin_top": 10.0,
		"modified": TS,
		"modified_by": "Administrator",
		"module": module,
		"name": name,
		"owner": "Administrator",
		"page_number": "Hide",
		"print_format_builder": 0,
		"print_format_builder_beta": 0,
		"print_format_for": "DocType",
		"print_format_type": "Jinja",
		"raw_printing": 0,
		"show_section_headings": 0,
		"standard": "Yes",
	}
	(path / f"{slug}.json").write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
	print("wrote", name)
