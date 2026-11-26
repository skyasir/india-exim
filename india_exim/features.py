"""Feature switches (India EXIM Settings): what this company does. They only decide what is shown.

The Business Type (Export, Import or Both) comes first: switches for exports count only when the
business exports.

A field behind a switch also shows whenever it holds a value, so nothing already entered is hidden,
and no check or calculation depends on a switch.
"""

import frappe
from frappe.utils import cint

BUSINESS_TYPES = ("Export", "Import", "Both")
FEATURES = {
	# switch in India EXIM Settings: key in frappe.boot.exim_features
	"claim_incentives": "incentives",
	"track_shipments": "shipments",
	"use_dgft_licences": "licences",
	"use_trade_agreements": "fta",
	"do_merchant_export": "merchant_export",
	"ship_special_cargo": "special_cargo",
	"use_ecgc": "ecgc",
}
EXPORT_ONLY = {"incentives", "shipments", "merchant_export", "special_cargo", "ecgc"}
MODULES = {
	"exports": "Exports",
	"imports": "Imports",
	"incentives": "Export Incentives",
	"licences": "DGFT Licences",
	"fta": "Trade Agreements",
	"shipments": "Trade Documents",
}


def get_features() -> dict[str, bool]:
	settings = frappe.get_cached_doc("India EXIM Settings")
	business_type = settings.get("business_type") or "Export"
	features = {"exports": business_type != "Import", "imports": business_type != "Export"}
	for field, key in FEATURES.items():
		on = bool(cint(settings.get(field)))
		features[key] = on and (features["exports"] or key not in EXPORT_ONLY)
	return features


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
