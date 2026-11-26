"""Generate standard Number Cards, Dashboard Charts, the India EXIM Dashboard and the home Workspace."""

import json
import re
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "india_exim"
TS = "2026-11-21 10:00:00.000000"
COMPANY = '"frappe.defaults.get_user_default(\\"Company\\")"'
THIS_FY = "(frappe.boot.current_fiscal_year || [null, `${frappe.datetime.get_today().slice(0,4)}-01-01`, `${frappe.datetime.get_today().slice(0,4)}-12-31`]).slice(1)"
TODAY = "frappe.datetime.get_today()"
OPEN_SB = ["Pending", "Partly Realised"]
CUSTOM = "india_exim.utils.dashboard"


def scrub(name):
	return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def module_dir(module):
	return APP / scrub(module)


def write(path, data):
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")


def card(
	name,
	module,
	doctype=None,
	function="Count",
	field=None,
	filters=(),
	dynamic=(),
	color=None,
	method=None,
	stats=True,
):
	data = {
		"creation": TS,
		"docstatus": 0,
		"doctype": "Number Card",
		"idx": 0,
		"is_public": 1,
		"is_standard": 1,
		"label": name,
		"modified": TS,
		"modified_by": "Administrator",
		"module": module,
		"name": name,
		"owner": "Administrator",
		"show_percentage_stats": int(stats),
		"stats_time_interval": "Monthly",
		"show_full_number": 1,
	}
	if method:
		data.update(
			{
				"type": "Custom",
				"method": method,
				"filters_json": "{}",
				"filters_config": "[]",
				"function": "Count",
			}
		)
	else:
		data.update(
			{
				"type": "Document Type",
				"document_type": doctype,
				"function": function,
				"filters_json": json.dumps([[doctype, *f] for f in filters]),
				"dynamic_filters_json": json.dumps([[doctype, f, op, expr] for f, op, expr in dynamic]),
			}
		)
		if field:
			data["aggregate_function_based_on"] = field
	if color:
		data["color"] = color
	write(module_dir(module) / "number_card" / scrub(name) / f"{scrub(name)}.json", data)
	return name


def chart(
	name,
	module,
	doctype,
	chart_type,
	type_,
	*,
	based_on=None,
	value=None,
	group_by=None,
	group_type="Count",
	filters=(),
	message="",
	groups=0,
	timespan="Last Year",
):
	data = {
		"chart_name": name,
		"chart_type": chart_type,
		"creation": TS,
		"docstatus": 0,
		"doctype": "Dashboard Chart",
		"document_type": doctype,
		"dynamic_filters_json": "",
		"empty_state_message": message,
		"filters_json": json.dumps([[doctype, *f] for f in filters]),
		"idx": 0,
		"is_public": 1,
		"is_standard": 1,
		"modified": TS,
		"modified_by": "Administrator",
		"module": module,
		"name": name,
		"number_of_groups": groups,
		"owner": "Administrator",
		"type": type_,
		"use_report_chart": 0,
		"y_axis": [],
		"timeseries": int(chart_type in ("Sum", "Count", "Average")),
		"time_interval": "Monthly",
		"timespan": timespan,
	}
	if based_on:
		data["based_on"] = based_on
	if value:
		data["value_based_on"] = value
	if group_by:
		data.update({"group_by_based_on": group_by, "group_by_type": group_type, "timeseries": 0})
		if value:
			data["aggregate_function_based_on"] = value
	write(module_dir(module) / "dashboard_chart" / scrub(name) / f"{scrub(name)}.json", data)
	return name


SUBMITTED = [("docstatus", "=", 1)]

# ---- Number cards
EXPORT_CARDS = [
	card(
		"Exports This Year (FOB)",
		"Exports",
		"Shipping Bill",
		"Sum",
		"total_fob_value_inr",
		SUBMITTED,
		[
			("company", "=", 'frappe.defaults.get_user_default("Company")'),
			("shipping_bill_date", "Between", THIS_FY),
		],
		"#2490EF",
	),
	card(
		"Awaiting LEO",
		"Exports",
		"Shipping Bill",
		filters=[*SUBMITTED, ("status", "=", "Filed")],
		dynamic=[("company", "=", 'frappe.defaults.get_user_default("Company")')],
		color="#ECAD4B",
		stats=False,
	),
	card(
		"Awaiting Realisation",
		"Exports",
		"Shipping Bill",
		filters=[*SUBMITTED, ("realisation_status", "in", OPEN_SB)],
		dynamic=[("company", "=", 'frappe.defaults.get_user_default("Company")')],
		color="#ECAD4B",
		stats=False,
	),
	card(
		"Realisation Overdue",
		"Exports",
		"Shipping Bill",
		filters=[*SUBMITTED, ("realisation_status", "in", OPEN_SB)],
		dynamic=[
			("company", "=", 'frappe.defaults.get_user_default("Company")'),
			("realisation_due_date", "<", TODAY),
		],
		color="#E24C4C",
		stats=False,
	),
	card(
		"Shipments in Progress",
		"Exports",
		"Export Shipment",
		filters=[("status", "not in", ["Delivered", "Closed", "Cancelled"])],
		dynamic=[("company", "=", 'frappe.defaults.get_user_default("Company")')],
		color="#2490EF",
		stats=False,
	),
	card(
		"Shipments with Pending Documents",
		"Exports",
		"Export Shipment",
		filters=[("status", "not in", ["Delivered", "Closed", "Cancelled"]), ("readiness_percent", "<", 100)],
		dynamic=[("company", "=", 'frappe.defaults.get_user_default("Company")')],
		color="#E24C4C",
		stats=False,
	),
]
INCENTIVE_CARDS = [
	card(
		"Incentives Receivable",
		"Export Incentives",
		method=f"{CUSTOM}.get_incentives_receivable",
		stats=False,
		color="#29CD42",
	),
	card(
		"Shipping Bills Not Yet Claimed",
		"Export Incentives",
		method=f"{CUSTOM}.get_unclaimed_shipping_bills",
		stats=False,
		color="#ECAD4B",
	),
	card(
		"RoDTEP Scrip Balance",
		"Export Incentives",
		"RoDTEP Scrip",
		"Sum",
		"balance_amount",
		[*SUBMITTED, ("status", "in", ["Active", "Partly Used"])],
		[("company", "=", 'frappe.defaults.get_user_default("Company")')],
		"#29CD42",
		stats=False,
	),
	card(
		"Days to LUT Expiry",
		"EXIM Setup",
		method=f"{CUSTOM}.get_days_to_lut_expiry",
		stats=False,
		color="#7575FF",
	),
]
IMPORT_CARDS = [
	card(
		"Customs Duty This Year",
		"Imports",
		"Bill of Entry",
		"Sum",
		"total_customs_duty",
		SUBMITTED,
		[
			("company", "=", 'frappe.defaults.get_user_default("Company")'),
			("bill_of_entry_date", "Between", THIS_FY),
		],
		"#7575FF",
	),
	card(
		"Import Payments Pending",
		"Imports",
		"Bill of Entry",
		filters=[*SUBMITTED, ("exim_payment_status", "!=", "Paid")],
		dynamic=[("company", "=", 'frappe.defaults.get_user_default("Company")')],
		color="#ECAD4B",
		stats=False,
	),
]

LICENCE_CARDS = [
	card(
		"Active Authorisations",
		"DGFT Licences",
		"Export Authorisation",
		filters=[("status", "=", "Active")],
		dynamic=[("company", "=", 'frappe.defaults.get_user_default("Company")')],
		color="#2490EF",
		stats=False,
	),
	card(
		"EO Due in 90 Days",
		"DGFT Licences",
		"Export Authorisation",
		filters=[("status", "=", "Active")],
		dynamic=[
			("company", "=", 'frappe.defaults.get_user_default("Company")'),
			("eo_period_upto", "<=", "frappe.datetime.add_days(frappe.datetime.get_today(), 90)"),
		],
		color="#E24C4C",
		stats=False,
	),
	card(
		"Duty Saved under Authorisations",
		"DGFT Licences",
		"Export Authorisation",
		"Sum",
		"total_duty_saved",
		[("status", "in", ["Active", "EO Fulfilled"])],
		[("company", "=", 'frappe.defaults.get_user_default("Company")')],
		"#29CD42",
		stats=False,
	),
]

FTA_CARDS = [
	card(
		"Certificates of Origin Pending",
		"Trade Agreements",
		"Certificate of Origin",
		filters=[("status", "in", ["Draft", "Applied"])],
		dynamic=[("company", "=", 'frappe.defaults.get_user_default("Company")')],
		color="#ECAD4B",
		stats=False,
	),
	card(
		"Duty Saved under Trade Agreements",
		"Trade Agreements",
		"Bill of Entry",
		"Sum",
		"exim_fta_duty_saved",
		[*SUBMITTED, ("exim_trade_agreement", "is", "set")],
		[("company", "=", 'frappe.defaults.get_user_default("Company")')],
		"#29CD42",
		stats=False,
	),
]

# ---- Charts
CHARTS = [
	chart(
		"Exports by Month (FOB INR)",
		"Exports",
		"Shipping Bill",
		"Sum",
		"Bar",
		based_on="shipping_bill_date",
		value="total_fob_value_inr",
		filters=SUBMITTED,
		message="FOB value of shipping bills filed each month.",
	),
	chart(
		"Exports by Destination",
		"Exports",
		"Shipping Bill",
		"Group By",
		"Donut",
		group_by="destination_country",
		group_type="Sum",
		value="total_fob_value_inr",
		filters=SUBMITTED,
		groups=6,
		message="Where your exports go, by FOB value.",
	),
	chart(
		"Top Export Customers",
		"Exports",
		"Shipping Bill",
		"Group By",
		"Bar",
		group_by="customer",
		group_type="Sum",
		value="total_fob_value_inr",
		filters=SUBMITTED,
		groups=8,
		message="Buyers by FOB value shipped.",
	),
	chart(
		"Export Realisation Status",
		"Exports",
		"Shipping Bill",
		"Group By",
		"Donut",
		group_by="realisation_status",
		filters=SUBMITTED,
		message="Shipping bills by payment realisation status (FEMA).",
	),
	chart(
		"Export Shipments by Status",
		"Exports",
		"Export Shipment",
		"Group By",
		"Percentage",
		group_by="status",
		filters=[("status", "!=", "Cancelled")],
		message="Where open shipments stand.",
	),
	chart(
		"Incentives Sanctioned by Month",
		"Export Incentives",
		"Export Incentive Claim",
		"Sum",
		"Bar",
		based_on="posting_date",
		value="total_sanctioned",
		filters=SUBMITTED,
		message="Drawback, RoDTEP and RoSCTL sanctioned by customs.",
	),
	chart(
		"Customs Duty by Month",
		"Imports",
		"Bill of Entry",
		"Sum",
		"Line",
		based_on="bill_of_entry_date",
		value="total_customs_duty",
		filters=SUBMITTED,
		message="Customs duty assessed on bills of entry.",
	),
]

# ---- Dashboard (standard Dashboard doctype, opened from the sidebar)
dashboard = {
	"cards": [{"card": name} for name in EXPORT_CARDS + INCENTIVE_CARDS + IMPORT_CARDS],
	"charts": [
		{"chart": "Exports by Month (FOB INR)", "width": "Full"},
		{"chart": "Exports by Destination", "width": "Half"},
		{"chart": "Export Realisation Status", "width": "Half"},
		{"chart": "Top Export Customers", "width": "Full"},
		{"chart": "Incentives Sanctioned by Month", "width": "Half"},
		{"chart": "Customs Duty by Month", "width": "Half"},
		{"chart": "Export Shipments by Status", "width": "Full"},
	],
	"creation": TS,
	"dashboard_name": "India EXIM",
	"docstatus": 0,
	"doctype": "Dashboard",
	"idx": 0,
	"is_default": 0,
	"is_standard": 1,
	"modified": TS,
	"modified_by": "Administrator",
	"module": "Exports",
	"name": "India EXIM",
	"owner": "Administrator",
}
write(module_dir("Exports") / "exports_dashboard" / "india_exim" / "india_exim.json", dashboard)

# ---- Home workspace
SHORTCUTS = [
	(
		"Export Shipment",
		"Orange",
		"{} In Progress",
		[["Export Shipment", "status", "not in", ["Delivered", "Closed", "Cancelled"]]],
	),
	("Shipping Bill", "Yellow", "{} Awaiting LEO", [["Shipping Bill", "status", "=", "Filed"]]),
	(
		"Export Incentive Claim",
		"Blue",
		"{} Awaiting Receipt",
		[["Export Incentive Claim", "status", "in", ["Sanctioned", "Partly Received"]]],
	),
	("RoDTEP Scrip", "Green", "{} Active", [["RoDTEP Scrip", "status", "in", ["Active", "Partly Used"]]]),
	(
		"Bill of Entry",
		"Purple",
		"{} Unpaid",
		[["Bill of Entry", "exim_payment_status", "!=", "Paid"], ["Bill of Entry", "docstatus", "=", 1]],
	),
	(
		"Sales Invoice",
		"Grey",
		"{} Export Invoices",
		[["Sales Invoice", "exim_is_export", "=", 1], ["Sales Invoice", "docstatus", "=", 1]],
	),
]
REPORT_SHORTCUTS = [
	("Export Realisation Ageing", "Shipping Bill", "Red"),
	("Export Incentive Register", "Shipping Bill", "Blue"),
	("Pending Trade Documents", "Export Shipment", "Orange"),
	("Shipping Bill Register", "Shipping Bill", "Grey"),
	("Shipment Tracker", "Export Shipment", "Blue"),
	("Customs Duty Register", "Bill of Entry", "Purple"),
	("Import Payment Ageing", "Bill of Entry", "Yellow"),
]


def block(id_, type_, data):
	return {"id": id_, "type": type_, "data": data}


def header(id_, text):
	return block(id_, "header", {"text": f'<span class="h4"><b>{text}</b></span>', "col": 12})


ONBOARDING = block("onboarding", "onboarding", {"onboarding_name": "India EXIM Onboarding", "col": 12})
content = [ONBOARDING, header("h_exports", "Exports")]
content += [block(scrub(c)[:12], "number_card", {"number_card_name": c, "col": 4}) for c in EXPORT_CARDS]
content += [block("c_month", "chart", {"chart_name": "Exports by Month (FOB INR)", "col": 12})]
content += [
	block("c_dest", "chart", {"chart_name": "Exports by Destination", "col": 6}),
	block("c_real", "chart", {"chart_name": "Export Realisation Status", "col": 6}),
]
content += [header("h_incent", "Incentives and GST Refunds")]
content += [block(scrub(c)[:12], "number_card", {"number_card_name": c, "col": 3}) for c in INCENTIVE_CARDS]
content += [header("h_imports", "Imports")]
content += [block(scrub(c)[:12], "number_card", {"number_card_name": c, "col": 6}) for c in IMPORT_CARDS]
content += [block("c_duty", "chart", {"chart_name": "Customs Duty by Month", "col": 12})]
REPORT_CARDS = [
	(
		"Export Reports",
		[
			"Shipping Bill Register",
			"Export Realisation Ageing",
			"Export Summary",
			"Export Advance Register",
			"Merchant Export Register",
			"Costing vs Actual",
		],
	),
	("Incentive Reports", ["Export Incentive Register", "LUT Register", "Authorisation Register"]),
	("Import Reports", ["Customs Duty Register", "Import Payment Ageing", "Bill of Entry Summary"]),
	("Shipment Reports", ["Shipment Tracker", "Pending Trade Documents"]),
]
LINKS = []
for card, reports in REPORT_CARDS:
	LINKS.append(
		{
			"hidden": 0,
			"is_query_report": 0,
			"label": card,
			"link_count": len(reports),
			"link_type": "DocType",
			"onboard": 0,
			"type": "Card Break",
		}
	)
	LINKS += [
		{
			"hidden": 0,
			"is_query_report": 1,
			"label": r,
			"link_count": 0,
			"link_to": r,
			"link_type": "Report",
			"onboard": 0,
			"type": "Link",
		}
		for r in reports
	]
content += [header("h_reports", "Reports")]
content += [
	block("r_" + scrub(card)[:10], "card", {"card_name": card, "col": 3}) for card, _reports in REPORT_CARDS
]
content += [header("h_quick", "Quick Access")]
content += [block("s_" + scrub(s[0])[:10], "shortcut", {"shortcut_name": s[0], "col": 4}) for s in SHORTCUTS]
content += [
	block("rs_" + scrub(r[0])[:10], "shortcut", {"shortcut_name": r[0], "col": 4}) for r in REPORT_SHORTCUTS
]

workspace = {
	"app": "india_exim",
	"charts": [
		{"chart_name": c, "label": c}
		for c in (
			"Exports by Month (FOB INR)",
			"Exports by Destination",
			"Export Realisation Status",
			"Customs Duty by Month",
		)
	],
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
	"label": "India EXIM",
	"links": LINKS,
	"modified": TS,
	"modified_by": "Administrator",
	"module": "Exports",
	"name": "India EXIM",
	"number_cards": [
		{"label": c, "number_card_name": c} for c in EXPORT_CARDS + INCENTIVE_CARDS + IMPORT_CARDS
	],
	"owner": "Administrator",
	"parent_page": "",
	"public": 1,
	"quick_lists": [],
	"restrict_to_domain": "",
	"roles": [
		{"role": "EXIM Manager"},
		{"role": "EXIM User"},
		{"role": "System Manager"},
		{"role": "Accounts Manager"},
	],
	"sequence_id": 30.0,
	"shortcuts": [
		{
			"label": label,
			"link_to": label,
			"type": "DocType",
			"color": color,
			"doc_view": "List",
			"format": fmt,
			"stats_filter": json.dumps(stats),
		}
		for label, color, fmt, stats in SHORTCUTS
	]
	+ [
		{
			"label": label,
			"link_to": label,
			"type": "Report",
			"report_ref_doctype": ref,
			"color": color,
			"doc_view": "",
			"format": "",
			"stats_filter": "",
		}
		for label, ref, color in REPORT_SHORTCUTS
	],
	"title": "India EXIM",
	"type": "Workspace",
}
write(APP / "exports" / "workspace" / "india_exim" / "india_exim.json", workspace)


# ---- One overview workspace per module. It shares the module sidebar's name, so the shell's own
# URL (/desk/exports) opens it and the dock lands on it instead of on the home page.
def open_stats(doctype, *filters):
	return json.dumps([[doctype, *f] for f in filters])


DOC_SHORTCUTS = {s[0]: s for s in SHORTCUTS}
REPORT_REFS = {r[0]: r for r in REPORT_SHORTCUTS}
MODULE_WORKSPACES = [
	{
		"name": "Exports",
		"icon": "ship",
		"sequence": 31.0,
		"cards": EXPORT_CARDS,
		"charts": [
			("Exports by Month (FOB INR)", 12),
			("Exports by Destination", 6),
			("Export Realisation Status", 6),
			("Top Export Customers", 12),
		],
		"report_cards": [REPORT_CARDS[0]],
		# in the order an export moves
		"doctypes": [
			(
				"Quotation",
				"Grey",
				"{} Open",
				open_stats("Quotation", ("exim_is_export", "=", 1), ("status", "=", "Open")),
			),
			("Export Costing Sheet", "Grey", "", "[]"),
			(
				"Sales Order",
				"Blue",
				"{} To Deliver",
				open_stats(
					"Sales Order",
					("exim_is_export", "=", 1),
					("status", "in", ["To Deliver and Bill", "To Deliver"]),
				),
			),
			("Proforma Invoice", "Grey", "", "[]"),
			("Delivery Note", "Grey", "", "[]"),
			"Sales Invoice",
			"Export Shipment",
			"Shipping Bill",
			("Payment Entry", "Grey", "", "[]"),
		],
		"reports": ["Export Realisation Ageing", "Shipping Bill Register"],
	},
	{
		"name": "Imports",
		"icon": "package-open",
		"sequence": 32.0,
		"cards": IMPORT_CARDS,
		"charts": [("Customs Duty by Month", 12)],
		"report_cards": [REPORT_CARDS[2]],
		"doctypes": [
			"Bill of Entry",
			(
				"Purchase Invoice",
				"Grey",
				"{} Import Invoices",
				open_stats("Purchase Invoice", ("exim_is_import", "=", 1), ("docstatus", "=", 1)),
			),
			("Landed Cost Voucher", "Grey", "", "[]"),
		],
		"reports": ["Customs Duty Register", "Import Payment Ageing"],
	},
	{
		"name": "Export Incentives",
		"icon": "badge-indian-rupee",
		"sequence": 33.0,
		"cards": INCENTIVE_CARDS,
		"charts": [("Incentives Sanctioned by Month", 12)],
		"report_cards": [REPORT_CARDS[1]],
		"doctypes": [
			"Export Incentive Claim",
			"RoDTEP Scrip",
			("GST Refund Claim", "Grey", "", "[]"),
			("Export Incentive Rate", "Grey", "", "[]"),
		],
		"reports": ["Export Incentive Register"],
	},
	{
		"name": "Trade Documents",
		"icon": "files",
		"sequence": 34.0,
		"cards": ["Shipments in Progress", "Shipments with Pending Documents"],
		"charts": [("Export Shipments by Status", 12)],
		"report_cards": [REPORT_CARDS[3]],
		"doctypes": [
			"Export Shipment",
			("Document Requirement Template", "Grey", "", "[]"),
			("Trade Document Type", "Grey", "", "[]"),
			("Country Group", "Grey", "", "[]"),
		],
		"reports": ["Shipment Tracker", "Pending Trade Documents"],
	},
	{
		"name": "DGFT Licences",
		"icon": "stamp",
		"sequence": 35.0,
		"cards": LICENCE_CARDS,
		"charts": [],
		"report_cards": [("Licence Reports", ["Authorisation Register"])],
		"doctypes": [
			(
				"Export Authorisation",
				"Blue",
				"{} Active",
				open_stats("Export Authorisation", ("status", "=", "Active")),
			),
			("Bill of Entry", "Grey", "", "[]"),
			("Shipping Bill", "Grey", "", "[]"),
		],
		"reports": [],
	},
	{
		"name": "Trade Agreements",
		"icon": "handshake",
		"sequence": 35.5,
		"cards": FTA_CARDS,
		"charts": [],
		"report_cards": [],
		"doctypes": [
			(
				"Certificate of Origin",
				"Orange",
				"{} Pending",
				open_stats("Certificate of Origin", ("status", "in", ["Draft", "Applied"])),
			),
			("Bill of Entry", "Grey", "", "[]"),
		],
		"reports": [],
	},
	{
		"name": "EXIM Setup",
		"icon": "settings",
		"sequence": 36.0,
		"cards": ["Days to LUT Expiry"],
		"charts": [],
		"report_cards": [("Setup Reports", ["LUT Register"])],
		"doctypes": [
			(d, "Grey", "", "[]")
			for d in (
				"India EXIM Settings",
				"Letter of Undertaking",
				"Customs Exchange Rate",
				"Customs Tariff Item",
				"Port Master",
				"Company",
				"Country",
			)
		],
		"reports": [],
	},
]


def module_workspace(spec):
	name = spec["name"]
	doctypes = [DOC_SHORTCUTS[d] if isinstance(d, str) else d for d in spec["doctypes"]]
	reports = [REPORT_REFS[r] for r in spec["reports"]]
	col = 12 // min(len(spec["cards"]), 3) if spec["cards"] else 4
	content = [ONBOARDING] if name == "EXIM Setup" else []
	content += [
		block("n_" + scrub(c)[:10], "number_card", {"number_card_name": c, "col": col}) for c in spec["cards"]
	]
	content += [block("c_" + scrub(c)[:10], "chart", {"chart_name": c, "col": w}) for c, w in spec["charts"]]
	content += [header("h_quick", "Quick Access")]
	content += [
		block("s_" + scrub(d[0])[:10], "shortcut", {"shortcut_name": d[0], "col": 4}) for d in doctypes
	]
	content += [
		block("rs_" + scrub(r[0])[:10], "shortcut", {"shortcut_name": r[0], "col": 4}) for r in reports
	]
	links = []
	if spec["report_cards"]:
		content += [header("h_reports", "Reports")]
		content += [
			block("r_" + scrub(c)[:10], "card", {"card_name": c, "col": 4}) for c, _r in spec["report_cards"]
		]
		for card_name, report_names in spec["report_cards"]:
			links.append(
				{
					"hidden": 0,
					"is_query_report": 0,
					"label": card_name,
					"link_count": len(report_names),
					"link_type": "DocType",
					"onboard": 0,
					"type": "Card Break",
				}
			)
			links += [
				{
					"hidden": 0,
					"is_query_report": 1,
					"label": r,
					"link_count": 0,
					"link_to": r,
					"link_type": "Report",
					"onboard": 0,
					"type": "Link",
				}
				for r in report_names
			]
	data = {
		"app": "india_exim",
		"charts": [{"chart_name": c, "label": c} for c, _w in spec["charts"]],
		"content": json.dumps(content),
		"creation": TS,
		"custom_blocks": [],
		"docstatus": 0,
		"doctype": "Workspace",
		"for_user": "",
		"hide_custom": 0,
		"icon": spec["icon"],
		"idx": 0,
		"is_hidden": 0,
		"label": name,
		"links": links,
		"modified": TS,
		"modified_by": "Administrator",
		"module": name,
		"name": name,
		"number_cards": [{"label": c, "number_card_name": c} for c in spec["cards"]],
		"owner": "Administrator",
		"parent_page": "",
		"public": 1,
		"quick_lists": [],
		"restrict_to_domain": "",
		"roles": workspace["roles"],
		"sequence_id": spec["sequence"],
		"shortcuts": [
			{
				"label": label,
				"link_to": label,
				"type": "DocType",
				"color": color,
				"doc_view": "List",
				"format": fmt,
				"stats_filter": stats if isinstance(stats, str) else json.dumps(stats),
			}
			for label, color, fmt, stats in doctypes
		]
		+ [
			{
				"label": label,
				"link_to": label,
				"type": "Report",
				"report_ref_doctype": ref,
				"color": color,
				"doc_view": "",
				"format": "",
				"stats_filter": "",
			}
			for label, ref, color in reports
		],
		"title": name,
		"type": "Workspace",
	}
	write(module_dir(name) / "workspace" / scrub(name) / f"{scrub(name)}.json", data)


for spec in MODULE_WORKSPACES:
	module_workspace(spec)

print("cards", len(EXPORT_CARDS + INCENTIVE_CARDS + IMPORT_CARDS), "charts", len(CHARTS))
