"""India EXIM onboarding: Onboarding Steps + one Module Onboarding, in the EXIM Setup module."""

import json
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "india_exim" / "exim_setup"
TS = "2026-11-24 20:00:00.000000"
ONBOARDING = "India EXIM Onboarding"

# (name, title, action, target, description, optional, extra)
STEPS = [
	(
		"EXIM Quick Setup",
		"Quick setup",
		"Go to Page",
		"Form/India EXIM Settings",
		"Press **Quick Setup**: IEC, AD code and port, LUT, and what you do. The accounts, tariff codes and RoDTEP rates are set up for you.",
		0,
		{},
	),
	(
		"EXIM Customs Exchange Rate",
		"Enter customs exchange rates",
		"Create Entry",
		"Customs Exchange Rate",
		"CBIC notifies export and import rates twice a month. Shipping bills and bills of entry use the rate in force on their date. You can also import them with Data Import.",
		0,
		{},
	),
	(
		"EXIM Export Customer",
		"Set up an overseas buyer",
		"Go to Page",
		"List/Customer",
		"Tick **Export Customer** on each overseas buyer and fill the Export Details tab: document instructions, denied-party screening and ECGC limit.",
		0,
		{},
	),
	(
		"EXIM First Quotation",
		"Make your first export quotation",
		"Create Entry",
		"Quotation",
		"Tick **Is Export** and fill the Export Details tab. The details carry through the Sales Order, Proforma Invoice, Delivery Note and Sales Invoice.",
		1,
		{},
	),
	(
		"EXIM Opening Balances",
		"Bring in open shipping bills",
		"Go to Page",
		"data-import",
		"Going live mid-year? Import the shipping bills still awaiting realisation or incentive claims, ticked **Is Opening Entry**, and the RoDTEP scrips in hand. Templates are in the app's `setup/import_templates` folder.",
		1,
		{},
	),
]


def scrub(name):
	return name.lower().replace(" ", "_")


for index, (name, title, action, target, description, _optional, extra) in enumerate(STEPS):
	data = {
		"action": action,
		"creation": TS,
		"description": description,
		"docstatus": 0,
		"doctype": "Onboarding Step",
		"idx": index,
		"is_complete": 0,
		"is_single": 0,
		"is_skipped": 0,
		"modified": TS,
		"modified_by": "Administrator",
		"name": name,
		"owner": "Administrator",
		"show_form_tour": 0,
		"show_full_form": 1,
		"title": title,
		"validate_action": 1,
		**extra,
	}
	if action == "Create Entry":
		data["reference_document"] = target
		data["action_label"] = f"Add {target}"
	else:
		data["path"] = target
		data["action_label"] = "Open"
	folder = APP / "onboarding_step" / scrub(name)
	folder.mkdir(parents=True, exist_ok=True)
	(folder / "__init__.py").touch()
	(APP / "onboarding_step" / "__init__.py").touch()
	(folder / f"{scrub(name)}.json").write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")

module_onboarding = {
	"allow_roles": [{"role": "EXIM Manager"}, {"role": "System Manager"}],
	"creation": TS,
	"docstatus": 0,
	"doctype": "Module Onboarding",
	"idx": 0,
	"is_complete": 0,
	"modified": TS,
	"modified_by": "Administrator",
	"module": "EXIM Setup",
	"name": ONBOARDING,
	"owner": "Administrator",
	"steps": [{"is_optional": optional, "step": name} for name, _t, _a, _x, _d, optional, _e in STEPS],
	"title": "Set up India EXIM",
}
folder = APP / "module_onboarding" / scrub(ONBOARDING)
folder.mkdir(parents=True, exist_ok=True)
(folder / "__init__.py").touch()
(APP / "module_onboarding" / "__init__.py").touch()
(folder / f"{scrub(ONBOARDING)}.json").write_text(
	json.dumps(module_onboarding, indent=1, sort_keys=True) + "\n"
)
print("steps", len(STEPS))
