"""Feature switches (India EXIM Settings): what this company does. They only decide what is shown.

A field behind a switch also shows whenever it holds a value, so nothing already entered is hidden,
and no check or calculation depends on a switch.
"""

import frappe
from frappe.utils import cint

FEATURES = {
	# switch in India EXIM Settings: key in frappe.boot.exim_features
	"do_imports": "imports",
	"claim_incentives": "incentives",
	"track_shipments": "shipments",
	"use_dgft_licences": "licences",
	"do_merchant_export": "merchant_export",
	"ship_special_cargo": "special_cargo",
	"use_ecgc": "ecgc",
}
MODULES = {
	"imports": "Imports",
	"incentives": "Export Incentives",
	"licences": "DGFT Licences",
	"shipments": "Trade Documents",
}


def get_features() -> dict[str, bool]:
	settings = frappe.get_cached_doc("India EXIM Settings")
	return {key: bool(cint(settings.get(field))) for field, key in FEATURES.items()}


def extend_bootinfo(bootinfo) -> None:
	"""Switches for the forms, and modules that are switched off leave the dock."""
	features = get_features()
	bootinfo.exim_features = features
	if not features["shipments"]:
		hide_export_shipment(bootinfo)
	hidden = {module for key, module in MODULES.items() if not features[key]}
	if not hidden:
		return

	def shown(row):
		return not (row.get("link_type") == "Sidebar" and row.get("link_to") in hidden)

	for app in bootinfo.get("app_data") or []:
		if app.get("app_name") == "india_exim":
			app["dock"] = [row for row in app.get("dock") or [] if shown(row)]
	dock = bootinfo.get("dock") or {}
	if dock.get("india_exim"):
		dock["india_exim"] = [row for row in dock["india_exim"] if shown(row)]


def hide_export_shipment(bootinfo) -> None:
	"""Export Shipment also sits among the documents of the Exports sidebar."""
	sidebar = (bootinfo.get("module_sidebars") or {}).get("Exports")
	if sidebar:
		sidebar["items"] = [
			row for row in sidebar.get("items") or [] if row.get("link_to") != "Export Shipment"
		]


def when(feature: str, *fields: str) -> str:
	"""depends_on for a field behind a switch: switched on, or already filled."""
	return "eval:" + " || ".join(
		[f"frappe.boot.exim_features?.{feature}", *(f"doc.{field}" for field in fields)]
	)
