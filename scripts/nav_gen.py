"""Generate Frappe 16.60 navigation for India EXIM: one Sidebar per module + the app Dock + home Workspace."""

import json
import os
import shutil
from glob import glob
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "india_exim"
# apps folder of a bench with frappe, erpnext and india_compliance, to check that linked doctypes and reports exist
UPSTREAM = Path(os.environ.get("BENCH_APPS", "~/frappe-bench/apps")).expanduser()
TS = "2026-11-20 21:00:00.000000"
HOME = "India EXIM"

# module -> (dock icon, [items]); item = (label, link_type, link_to, icon) or ("section", label, icon)
SIDEBARS = {
	"Exports": (
		"ship",
		[
			("Overview", "Workspace", "Exports", "layout-dashboard"),
			("Home", "Workspace", HOME, "house"),
			("Dashboard", "Dashboard", "India EXIM", "chart-column"),
			# in the order an export moves: quote, order, proforma, dispatch, invoice, ship, get paid
			("Quotation", "DocType", "Quotation", "scroll-text"),
			("Export Costing Sheet", "DocType", "Export Costing Sheet", "calculator"),
			("Sales Order", "DocType", "Sales Order", "file-pen"),
			("Proforma Invoice", "DocType", "Proforma Invoice", "file-badge"),
			("Delivery Note", "DocType", "Delivery Note", "truck"),
			("Sales Invoice", "DocType", "Sales Invoice", "receipt"),
			("Export Shipment", "DocType", "Export Shipment", "container"),
			("Control Tower", "Page", "shipment-control-tower", "radar"),
			("Shipping Bill", "DocType", "Shipping Bill", "file-output"),
			("Payment Entry", "DocType", "Payment Entry", "landmark"),
			("section", "Reports", "notepad-text"),
			("Shipping Bill Register", "Report", "Shipping Bill Register", None),
			("Export Realisation Ageing", "Report", "Export Realisation Ageing", None),
			("Export Summary", "Report", "Export Summary", None),
			("Export Advance Register", "Report", "Export Advance Register", None),
			("Merchant Export Register", "Report", "Merchant Export Register", None),
			("Costing vs Actual", "Report", "Costing vs Actual", None),
			("Shipment Tracker", "Report", "Shipment Tracker", None),
		],
	),
	"Imports": (
		"package-open",
		[
			("Overview", "Workspace", "Imports", "layout-dashboard"),
			("Home", "Workspace", HOME, "house"),
			("Dashboard", "Dashboard", "India EXIM", "chart-column"),
			("Purchase Invoice", "DocType", "Purchase Invoice", "receipt"),
			("Bill of Entry", "DocType", "Bill of Entry", "file-input"),
			("Landed Cost Voucher", "DocType", "Landed Cost Voucher", "package-plus"),
			("Payment Entry", "DocType", "Payment Entry", "landmark"),
			("section", "Reports", "notepad-text"),
			("Customs Duty Register", "Report", "Customs Duty Register", None),
			("Import Payment Ageing", "Report", "Import Payment Ageing", None),
			("Bill of Entry Summary", "Report", "Bill of Entry Summary", None),
		],
	),
	"Export Incentives": (
		"badge-indian-rupee",
		[
			("Overview", "Workspace", "Export Incentives", "layout-dashboard"),
			("Home", "Workspace", HOME, "house"),
			("Dashboard", "Dashboard", "India EXIM", "chart-column"),
			("Export Incentive Claim", "DocType", "Export Incentive Claim", "hand-coins"),
			("RoDTEP Scrip", "DocType", "RoDTEP Scrip", "ticket"),
			("GST Refund Claim", "DocType", "GST Refund Claim", "receipt-indian-rupee"),
			("section", "Reports", "notepad-text"),
			("Export Incentive Register", "Report", "Export Incentive Register", None),
			("RoDTEP Scrip Ledger", "Report", "RoDTEP Scrip Ledger", None),
			("section", "Rates", "percent"),
			("Export Incentive Rate", "DocType", "Export Incentive Rate", None),
		],
	),
	"Trade Documents": (
		"files",
		[
			("Overview", "Workspace", "Trade Documents", "layout-dashboard"),
			("Home", "Workspace", HOME, "house"),
			("Dashboard", "Dashboard", "India EXIM", "chart-column"),
			("Control Tower", "Page", "shipment-control-tower", "radar"),
			("Document Board", "Page", "document-board", "kanban"),
			("Export Shipment", "DocType", "Export Shipment", "container"),
			("Document Requirement Template", "DocType", "Document Requirement Template", "list-checks"),
			("Trade Document Type", "DocType", "Trade Document Type", "file-text"),
			("Country Group", "DocType", "Country Group", "globe"),
			("section", "Reports", "notepad-text"),
			("Shipment Tracker", "Report", "Shipment Tracker", None),
			("Pending Trade Documents", "Report", "Pending Trade Documents", None),
		],
	),
	"EXIM Setup": (
		"settings",
		[
			("Overview", "Workspace", "EXIM Setup", "layout-dashboard"),
			("Home", "Workspace", HOME, "house"),
			("Dashboard", "Dashboard", "India EXIM", "chart-column"),
			("India EXIM Settings", "DocType", "India EXIM Settings", "sliders-horizontal"),
			("Customs Tariff Item", "DocType", "Customs Tariff Item", "barcode"),
			("Customs Exchange Rate", "DocType", "Customs Exchange Rate", "arrow-left-right"),
			("Letter of Undertaking", "DocType", "Letter of Undertaking", "file-signature"),
			("AD Code Registration", "DocType", "AD Code Registration", "building-2"),
			("Company", "DocType", "Company", "building"),
			("Country", "DocType", "Country", "flag"),
			("section", "Reports", "notepad-text"),
			("LUT Register", "Report", "LUT Register", None),
		],
	),
}


def scrub(name):
	return name.lower().replace(" ", "_").replace("-", "_")


def exists(link_type, link_to):
	if link_type in ("Workspace", "Dashboard", "Page"):
		return True
	kind = {"DocType": "doctype", "Report": "report"}[link_type]
	slug = scrub(link_to)
	return bool(glob(str(APP / "*" / kind / slug)) or glob(str(UPSTREAM / "*" / "*" / "*" / kind / slug)))


def build_items(entries):
	items, pending_section = [], None
	in_section = False
	for entry in entries:
		if entry[0] == "section":
			pending_section = entry
			continue
		label, link_type, link_to, icon = entry
		if not exists(link_type, link_to):
			continue
		if pending_section:
			items.append(
				item("Section Break", pending_section[1], icon=pending_section[2], indent=1, keep_closed=1)
			)
			pending_section, in_section = None, True
		items.append(item("Link", label, link_type, link_to, icon, child=int(in_section)))
	return items


def item(type_, label, link_type="DocType", link_to=None, icon=None, child=0, indent=0, keep_closed=0):
	row = {
		"added": 0,
		"child": child,
		"collapsible": 1,
		"hidden": 0,
		"indent": indent,
		"is_default_module": 0,
		"keep_closed": keep_closed,
		"label": label,
		"link_type": link_type,
		"open_in_new_tab": 0,
		"show_arrow": 0,
		"type": type_,
	}
	if link_to:
		row["link_to"] = link_to
	if icon:
		row["icon"] = icon
	return row


def write(path: Path, data: dict):
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")


def write_sidebars():
	for module, (icon, entries) in SIDEBARS.items():
		data = {
			"app": "india_exim",
			"creation": TS,
			"docstatus": 0,
			"doctype": "Sidebar",
			"header_icon": icon,
			"idx": 0,
			"items": build_items(entries),
			"modified": TS,
			"modified_by": "Administrator",
			"module": module,
			"name": module,
			"owner": "Administrator",
			"standard": 1,
			"title": module,
		}
		write(APP / scrub(module) / "sidebar" / scrub(module) / f"{scrub(module)}.json", data)


def write_dock():
	items = [
		{"added": 0, "hidden": 0, "icon": "house", "link_to": HOME, "link_type": "Workspace", "title": "Home"}
	]
	items += [
		{"added": 0, "hidden": 0, "icon": icon, "link_to": module, "link_type": "Sidebar", "title": module}
		for module, (icon, _entries) in SIDEBARS.items()
	]
	data = {
		"app": "india_exim",
		"creation": TS,
		"docstatus": 0,
		"doctype": "Dock",
		"idx": 0,
		"items": items,
		"modified": TS,
		"modified_by": "Administrator",
		"name": "india_exim",
		"owner": "Administrator",
		"standard": 1,
		"user": "",
	}
	write(APP / "dock" / "india_exim" / "india_exim.json", data)


def write_workspace(number_cards=(), charts=(), shortcuts=()):
	content = []
	for card in number_cards:
		content.append(
			{"id": scrub(card)[:10], "type": "number_card", "data": {"number_card_name": card, "col": 3}}
		)
	for chart in charts:
		content.append({"id": scrub(chart)[:10], "type": "chart", "data": {"chart_name": chart, "col": 6}})
	if shortcuts:
		content.append(
			{
				"id": "quick_head",
				"type": "header",
				"data": {"text": '<span class="h4"><b>Quick Access</b></span>', "col": 12},
			}
		)
		for shortcut in shortcuts:
			content.append(
				{
					"id": scrub(shortcut)[:10],
					"type": "shortcut",
					"data": {"shortcut_name": shortcut, "col": 3},
				}
			)
	data = {
		"app": "india_exim",
		"charts": [{"chart_name": c, "label": c} for c in charts],
		"content": json.dumps(content),
		"creation": TS,
		"custom_blocks": [],
		"docstatus": 0,
		"doctype": "Workspace",
		"for_user": "",
		"hide_custom": 0,
		"icon": "ship",
		"idx": 0,
		"is_hidden": 0,
		"label": HOME,
		"links": [],
		"modified": TS,
		"modified_by": "Administrator",
		"module": "Exports",
		"name": HOME,
		"number_cards": [{"label": c, "number_card_name": c} for c in number_cards],
		"owner": "Administrator",
		"parent_page": "",
		"public": 1,
		"quick_lists": [],
		"restrict_to_domain": "",
		"roles": [{"role": "EXIM Manager"}, {"role": "EXIM User"}, {"role": "System Manager"}],
		"sequence_id": 30.0,
		"shortcuts": [
			{"label": s, "link_to": s, "type": "DocType", "color": "Grey", "doc_view": "List"}
			for s in shortcuts
		],
		"title": HOME,
		"type": "Workspace",
	}
	write(APP / "exports" / "workspace" / "india_exim" / "india_exim.json", data)


def write_all(number_cards=(), charts=(), shortcuts=()):
	shutil.rmtree(APP / "workspace_sidebar", ignore_errors=True)
	write_sidebars()
	write_dock()  # the home workspace is written by dash_gen.py


if __name__ == "__main__":
	write_all(
		shortcuts=("Customs Tariff Item", "Letter of Undertaking", "Trade Document Type", "Bill of Entry")
	)
