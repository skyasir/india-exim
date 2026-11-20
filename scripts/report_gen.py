"""Create the JSON and __init__ of India EXIM script reports (the .py and .js are written by hand)."""

import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "india_exim"
TS = "2026-11-20 20:00:00.000000"
ROLES = ["EXIM Manager", "EXIM User", "Accounts Manager", "Accounts User", "Auditor"]
REPORTS = {
	# name: (module folder, module, ref doctype, add_total_row)
	"Export Advance Register": ("exports", "Exports", "Payment Entry", 1),
	"Shipment Tracker": ("trade_documents", "Trade Documents", "Export Shipment", 0),
	"Export Summary": ("exports", "Exports", "Shipping Bill", 1),
	"LUT Register": ("exim_setup", "EXIM Setup", "Letter of Undertaking", 1),
	"Merchant Export Register": ("exports", "Exports", "Purchase Invoice", 1),
	"Costing vs Actual": ("exports", "Exports", "Export Costing Sheet", 1),
	"Authorisation Register": ("dgft_licences", "DGFT Licences", "Export Authorisation", 1),
}

for name in sys.argv[1:] or REPORTS:
	folder, module, ref, total = REPORTS[name]
	slug = name.lower().replace(" ", "_")
	path = APP / folder / "report" / slug
	path.mkdir(parents=True, exist_ok=True)
	(APP / folder / "report" / "__init__.py").touch()
	(path / "__init__.py").touch()
	data = {
		"add_total_row": total,
		"columns": [],
		"creation": TS,
		"disabled": 0,
		"docstatus": 0,
		"doctype": "Report",
		"filters": [],
		"idx": 0,
		"is_standard": "Yes",
		"modified": TS,
		"modified_by": "Administrator",
		"module": module,
		"name": name,
		"owner": "Administrator",
		"prepared_report": 0,
		"ref_doctype": ref,
		"report_name": name,
		"report_type": "Script Report",
		"roles": [{"role": role} for role in ROLES],
	}
	(path / f"{slug}.json").write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
	print("wrote", path)
