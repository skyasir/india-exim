from doctype_gen import doctype, perms

SETUP = "EXIM Setup"
EXPORTS = "eval:doc.business_type != 'Import'"
DOCS = "Trade Documents"
MANAGER_ONLY = [
	("System Manager", "full"),
	("EXIM Manager", "full"),
	("EXIM User", "read"),
	("Accounts User", "read"),
]

doctype(
	"India EXIM Settings",
	SETUP,
	[
		"features_section:Section Break:What You Do|desc=Only what you do is shown on forms, in settings and in the menu. Nothing already entered is hidden, and no check depends on these.",
		"business_type:Select:Business Type|opt=Export\\nImport\\nBoth|default=Export|reqd|bold|desc=Exports only, imports only, or both. Menus, fields and settings of the other side are hidden.",
		"claim_incentives:Check:Duty Drawback, RoDTEP and Other Incentives|default=1|depends=" + EXPORTS,
		"track_shipments:Check:Shipment Tracking and Document Checklist (Export Shipment)|default=0|depends="
		+ EXPORTS,
		"use_dgft_licences:Check:DGFT Licences (Advance Authorisation, EPCG)|default=0",
		"column_break_features:Column Break",
		"do_merchant_export:Check:Merchant Export (buying at 0.1% GST)|default=0|depends=" + EXPORTS,
		"ship_special_cargo:Check:Dangerous Goods or Temperature-controlled Cargo|default=0|depends="
		+ EXPORTS,
		"use_ecgc:Check:ECGC Credit Cover|default=0|depends=" + EXPORTS,
		"checks_section:Section Break:Checks",
		"lut_check:Select:Check LUT on Zero-rated Exports|opt=Block\\nWarn\\nOff|default=Block|depends="
		+ EXPORTS
		+ "|desc=Exports without IGST (Overseas / SEZ) require a valid Letter of Undertaking for the invoice date.",
		"checklist_gate:Select:When Mandatory Documents Are Pending|opt=Warn\\nBlock\\nOff|default=Warn",
		"column_break_checks:Column Break",
		"pre_shipment_checks:Select:Pre-shipment Checks|opt=Off\\nWarn\\nBlock|default=Warn|depends="
		+ EXPORTS
		+ "|desc=Block stops a sanctioned destination, prohibited goods or an unscreened buyer; Warn only shows a message. Restricted goods and SCOMET items always warn.",
		"incentive_accrual_point:Select:Book Incentive Income On|opt=On LEO\\nOn Scroll\\nOn Receipt|default=On LEO|depends=eval:doc.business_type != 'Import' && doc.claim_incentives|desc=When Duty Drawback / RoDTEP is recognised as income. LEO is the usual choice because the entitlement is reasonably certain once the shipping bill carries the claim; confirm with your auditor.",
		"advanced_tab:Tab Break:Advanced",
		"incentives_section:Section Break:Alerts and Incentives|depends=eval:doc.business_type != 'Import' && doc.claim_incentives",
		"incentive_unclaimed_alert_days:Int:Alert When Incentive Unclaimed For (Days)|default=60",
		"column_break_inc:Column Break",
		"scrip_validity_months:Int:RoDTEP Scrip Validity (Months)|default=24|desc=Two years since Notification 79/2022-Customs (N.T.). Used when an e-scrip is recorded.",
		"fema_section:Section Break:FEMA / RBI|desc=RBI sets these periods by regulation and changes them from a date. Each row applies to shipping bills, advances or bills of entry dated on or after its Effective From, so older documents keep the period that applied to them.",
		"fema_periods:Table:Periods|opt=FEMA Period",
		"realisation_alert_days:Int:Alert Before Realisation Due (Days)|default=30",
		"gst_section:Section Break:GST on Exports|depends=eval:doc.business_type != 'Import' && doc.do_merchant_export",
		"merchant_export_days:Int:Merchant Export Within (Days)|default=90|desc=Goods bought at 0.1% GST for merchant export must be exported within this period from the supplier's invoice date.",
		"imports_section:Section Break:Imports|depends=eval:doc.business_type != 'Export'",
		"capitalise_customs_duty:Check:Add Non-creditable Customs Duty to Stock Value|default=1|desc=BCD, SWS and other non-creditable duties computed on the Bill of Entry are moved into item valuation through a Landed Cost Voucher.",
		"controls_section:Section Break:Buyer Screening|depends=" + EXPORTS,
		"buyer_screening_months:Int:Buyer Screening Valid For (Months)|default=12|desc=How long a denied-party screening of a buyer counts. 0 turns the screening check off.",
	],
	issingle=True,
	roles=[("System Manager", "full"), ("EXIM Manager", "full"), ("EXIM User", "read")],
	extra={"creation": "2026-11-19 13:00:00.000000", "modified": "2026-11-26 15:00:00.000000"},
)

doctype(
	"FEMA Period",
	SETUP,
	[
		"period_for:Select:Period For|opt=Export Realisation\\nShipment Against Advance\\nImport Payment|reqd|list|width=3",
		"effective_from:Date:Effective From|reqd|list|width=2|desc=Applies to documents dated on or after this date (shipping bill, advance receipt or bill of entry date).",
		"months:Int:Months|reqd|list|width=1",
		"reference:Data:RBI Reference|list|width=4|desc=e.g. FEM (Export of Goods and Services) (Second Amendment) Regulations, 2025",
	],
	istable=True,
	extra={"creation": "2026-11-24 18:00:00.000000", "modified": "2026-11-24 18:00:00.000000"},
)

doctype(
	"Port AD Code",
	SETUP,
	[
		"company:Link:Company|opt=Company|reqd|list|width=2",
		"ad_code:Data:AD Code|reqd|list|length=20|width=2",
		"bank:Link:Bank|opt=Bank|list|width=2",
		"bank_account:Link:Bank Account|opt=Bank Account|width=2",
		"port_address:Link:Port Address|opt=Address|width=2|desc=Used as the dispatch address on export e-Way Bills from this port.",
		"is_default:Check:Default|list|width=1|desc=The AD code used when the company has more than one at this port.",
	],
	istable=True,
	extra={"creation": "2026-11-26 14:00:00.000000", "modified": "2026-11-26 14:00:00.000000"},
)

doctype(
	"Port Master",
	SETUP,
	[
		"port_code:Data:Port Code|reqd|length=15|desc=UN/LOCODE, e.g. AEJEA for Jebel Ali. Indian ports use their customs port code, e.g. INNSA1 for Nhava Sheva.",
		"port_name:Data:Port Name|reqd|list|bold",
		"column_break_1:Column Break",
		"port_country:Link:Country|opt=Country|list|filter|qe|iup|desc=Taken from the first two letters of a UN/LOCODE when left empty.",
		"port_type:Select:Type|opt=\\nSea\\nAir\\nICD / CFS / SEZ\\nRail\\nLand Border\\nForeign Post Office|list|filter|qe",
		"disabled:Check:Disabled",
		{
			"fieldname": "ad_codes_section",
			"fieldtype": "Section Break",
			"label": "AD Codes",
			"depends_on": "eval:doc.port_country == 'India'",
			"description": "Authorised Dealer codes registered with Customs (ICEGATE) at this port, one per bank branch. The shipping bill takes the AD code from here.",
			"permlevel": 1,
		},
		{
			"fieldname": "ad_codes",
			"fieldtype": "Table",
			"label": "AD Codes",
			"options": "Port AD Code",
			"permlevel": 1,
		},
	],
	autoname="field:port_code",
	naming_rule="By fieldname",
	title_field="port_name",
	search_fields="port_name,port_country",
	sort_field="port_code",
	quick_entry=True,
	extra={
		"allow_rename": 1,
		"creation": "2026-11-26 14:00:00.000000",
		"modified": "2026-11-26 14:00:00.000000",
		# anyone who makes sales or purchase documents can add a port; AD codes are for EXIM managers
		"permissions": perms(
			[
				("System Manager", "full"),
				("EXIM Manager", "full"),
				("EXIM User", "write"),
				("Sales User", "write"),
				("Purchase User", "write"),
				("Accounts User", "read"),
			]
		)
		+ [
			{"role": role, "permlevel": 1, "read": 1, **({"write": 1} if write else {})}
			for role, write in (
				("System Manager", 1),
				("EXIM Manager", 1),
				("EXIM User", 0),
				("Sales User", 0),
				("Purchase User", 0),
				("Accounts User", 0),
			)
		],
	},
)

doctype(
	"Customs Tariff Item",
	SETUP,
	[
		"tariff_code:Data:Tariff Code (ITC-HS)|reqd|unique|list|length=8|desc=8-digit ITC-HS / Customs Tariff code.",
		"description:Small Text:Description|reqd|list",
		"column_break_1:Column Break",
		"chapter:Data:Chapter|ro|filter|length=2",
		"uqc:Link:Unit Quantity Code (UQC)|opt=UOM",
		"gst_hsn_code:Link:GST HSN Code|opt=GST HSN Code",
		"policy_section:Section Break:Trade Policy",
		"export_policy:Select:Export Policy|opt=\\nFree\\nRestricted\\nProhibited\\nSTE|default=Free|filter|desc=Empty when not yet checked against ITC-HS Schedule 2.",
		"import_policy:Select:Import Policy|opt=\\nFree\\nRestricted\\nProhibited\\nSTE|default=Free|filter|desc=Empty when not yet checked against ITC-HS Schedule 1.",
		"column_break_2:Column Break",
		"is_scomet:Check:SCOMET / Dual-use Item",
		"policy_notes:Small Text:Policy Conditions",
		"data_source:Data:Source|ro|desc=Set when the tariff item was loaded from India EXIM's tariff data.",
		"rates_section:Section Break:Customs Duty Rates|depends=eval:[frappe.boot.exim_features?.imports, (doc.rates ?? []).length].some(Boolean)|desc=Import duty, used on Bills of Entry. Leave empty if you only export.",
		"rates:Table:Rates|opt=Customs Tariff Rate",
	],
	autoname="field:tariff_code",
	naming_rule="By fieldname",
	title_field="description",
	search_fields="description,chapter",
	roles=MANAGER_ONLY,
	extra={"modified": "2026-11-24 22:00:00.000000"},
)

doctype(
	"Customs Tariff Rate",
	SETUP,
	[
		"effective_from:Date:Effective From|reqd|list|width=2",
		"effective_to:Date:Effective To|list|width=2",
		"bcd_rate:Percent:BCD %|list|width=1",
		"sws_rate:Percent:SWS % of BCD|default=10|list|width=1",
		"aidc_rate:Percent:AIDC %|list|width=1",
		"other_duty_rate:Percent:Other Duty %|width=1",
		"notification:Data:Notification No.|list|width=2",
	],
	istable=True,
)

doctype(
	"Export Incentive Rate",
	SETUP,
	[
		"scheme:Select:Scheme|opt=RoDTEP\\nDuty Drawback\\nRoSCTL|reqd|list|filter",
		"customs_tariff_item:Link:Tariff Item|opt=Customs Tariff Item|mandatory_depends=eval:!(doc.schedule_serial_no && doc.scheme != 'RoDTEP')|list|filter|desc=Leave empty for a schedule entry: it applies to every ITC-HS code of its heading.",
		"description:Small Text:Description|fetch=customs_tariff_item.description",
		"schedule_serial_no:Data:Schedule Serial No.|list|search|desc=Drawback schedule serial number (DBK Sr. No.) where applicable.",
		"item_code:Link:Only for Item (Brand Rate)|opt=Item|depends=eval:doc.scheme == 'Duty Drawback'|desc=Brand rate of drawback fixed by Customs for this product only. Leave empty for a rate that applies to every item of the tariff code.",
		"column_break_1:Column Break",
		"rate:Percent:Rate % of FOB|list|desc=0 for entries listed with no benefit (NIL).",
		"amount_per_unit:Currency:Fixed Amount Per Unit (INR)|opt=INR|desc=For entries notified as a fixed amount per unit instead of a % of FOB.",
		"cap_per_unit:Currency:Cap Per Unit (INR)|opt=INR|desc=Leave 0 when the schedule has no per-unit cap.",
		"cap_uom:Link:Cap Unit|opt=UOM|mandatory_depends=eval:doc.cap_per_unit",
		"central_rate:Percent:Central Levies % of FOB|depends=eval:doc.scheme == 'RoSCTL'|desc=RoSCTL is notified as a State and a Central rate, each with its own cap. Enter the State rate above.",
		"central_cap_per_unit:Currency:Central Cap Per Unit (INR)|opt=INR|depends=eval:doc.scheme == 'RoSCTL'",
		"validity_section:Section Break:Validity",
		"effective_from:Date:Effective From|reqd|list",
		"effective_to:Date:Effective To",
		"column_break_2:Column Break",
		"notification:Data:Notification No.",
		"data_source:Data:Source|ro|desc=Set when the rate was loaded from India EXIM's tariff data.",
	],
	autoname="hash",
	search_fields="scheme,customs_tariff_item,schedule_serial_no",
	roles=MANAGER_ONLY,
	extra={"modified": "2026-11-25 18:00:00.000000"},
)

doctype(
	"Customs Exchange Rate",
	SETUP,
	[
		"currency:Link:Currency|opt=Currency|reqd|list|filter",
		"effective_from:Date:Effective From|reqd|list",
		"notification:Data:CBIC Notification No.",
		"column_break_1:Column Break",
		"export_rate:Float:Export Rate (INR)|reqd|list|precision=4|desc=Rate notified by CBIC for exported goods; used for FOB in INR on shipping bills.",
		"import_rate:Float:Import Rate (INR)|reqd|list|precision=4|desc=Rate notified by CBIC for imported goods; used for assessable value on bills of entry.",
	],
	autoname="format:{currency}-{effective_from}",
	naming_rule="Expression",
	sort_field="effective_from",
	roles=MANAGER_ONLY,
)

doctype(
	"Letter of Undertaking",
	SETUP,
	[
		"company:Link:Company|opt=Company|reqd|list|filter",
		"fiscal_year:Link:Fiscal Year|opt=Fiscal Year|reqd|list|filter",
		"arn:Data:ARN|reqd|list|desc=Acknowledgement Reference Number of the LUT (GST RFD-11).",
		"column_break_1:Column Break",
		"filed_on:Date:Filed On|reqd",
		"valid_from:Date:Valid From|reqd",
		"valid_upto:Date:Valid Upto|reqd|list",
	],
	autoname="format:LUT-{fiscal_year}-{company}",
	naming_rule="Expression",
	title_field="arn",
	roles=[
		("System Manager", "full"),
		("EXIM Manager", "full"),
		("Accounts Manager", "full"),
		("EXIM User", "read"),
		("Accounts User", "read"),
	],
)

doctype(
	"Country Group",
	DOCS,
	[
		"group_name:Data:Group Name|reqd|unique",
		"description:Small Text:Description",
		"countries:Table MultiSelect:Countries|opt=Country Group Member|reqd",
	],
	autoname="field:group_name",
	naming_rule="By fieldname",
	roles=MANAGER_ONLY,
)

doctype(
	"Country Group Member",
	DOCS,
	["country:Link:Country|opt=Country|reqd|list"],
	istable=True,
)

doctype(
	"Trade Document Type",
	DOCS,
	[
		"document_name:Data:Document Name|reqd|unique|list",
		"category:Select:Category|opt=Commercial\\nTransport\\nOrigin\\nRegulatory\\nFinancial\\nProduct Certificate\\nCustoms\\nInsurance|reqd|list|filter",
		"direction:Select:Used For|opt=Export\\nImport\\nBoth|default=Both|filter",
		"issued_by:Select:Issued By|opt=Self\\nCHA\\nFreight Forwarder\\nShipping Line / Airline\\nChamber of Commerce\\nDGFT\\nCustoms\\nExport Inspection Council\\nGovernment Lab / Authority\\nThird-party Inspection Agency\\nEmbassy / Consulate\\nInsurance Company\\nBank\\nBuyer|reqd|list",
		"column_break_1:Column Break",
		"originals:Int:Originals Required|default=1",
		"copies:Int:Copies Required|default=0",
		"needs_legalisation:Check:Needs Legalisation / Apostille",
		"lead_time_days:Int:Typical Lead Time (Days)",
		"validity_days:Int:Validity (Days)",
		"generation_section:Section Break:Generation",
		"generated_in_system:Check:Generated in ERPNext",
		"print_format:Link:Print Format|opt=Print Format|depends=generated_in_system",
		"instructions:Text Editor:Instructions",
		"disabled:Check:Disabled",
	],
	autoname="field:document_name",
	naming_rule="By fieldname",
	search_fields="category,issued_by",
	roles=MANAGER_ONLY,
)
