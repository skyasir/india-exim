from doctype_gen import doctype

SETUP = "EXIM Setup"
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
		"incentives_section:Section Break:Export Incentives",
		"incentive_accrual_point:Select:Book Incentive Income On|opt=On LEO\\nOn Scroll\\nOn Receipt|default=On LEO|desc=When Duty Drawback / RoDTEP is recognised as income. LEO is the usual choice because the entitlement is reasonably certain once the shipping bill carries the claim; confirm with your auditor.",
		"column_break_inc:Column Break",
		"incentive_unclaimed_alert_days:Int:Alert When Incentive Unclaimed For (Days)|default=60",
		"scrip_validity_months:Int:RoDTEP Scrip Validity (Months)|default=12|desc=Default validity used when recording an e-scrip. Check the validity printed on the scrip.",
		"fema_section:Section Break:FEMA / RBI",
		"export_realisation_months:Int:Export Realisation Period (Months)|default=9|reqd|desc=Period from shipment within which export proceeds must be realised under the RBI Master Direction in force. Update this if RBI changes it.",
		"import_payment_months:Int:Import Payment Period (Months)|default=6|reqd|desc=Period from shipment within which import payments are expected to be settled.",
		"column_break_fema:Column Break",
		"realisation_alert_days:Int:Alert Before Realisation Due (Days)|default=30",
		"gst_section:Section Break:GST on Exports",
		"lut_check:Select:Check LUT on Zero-rated Exports|opt=Block\\nWarn\\nOff|default=Block|desc=Exports without IGST (Overseas / SEZ) require a valid Letter of Undertaking for the invoice date.",
		"imports_section:Section Break:Imports",
		"capitalise_customs_duty:Check:Add Non-creditable Customs Duty to Stock Value|default=1|desc=BCD, SWS and other non-creditable duties computed on the Bill of Entry are moved into item valuation through a Landed Cost Voucher.",
		"documents_section:Section Break:Trade Documents",
		"checklist_gate:Select:When Mandatory Documents Are Pending|opt=Warn\\nBlock\\nOff|default=Warn",
	],
	issingle=True,
	roles=[("System Manager", "full"), ("EXIM Manager", "full"), ("EXIM User", "read")],
)

doctype(
	"AD Code Registration",
	SETUP,
	[
		"company:Link:Company|opt=Company|reqd|list|filter",
		"ad_code:Data:AD Code|reqd|list|length=20|desc=Authorised Dealer code registered with Customs (ICEGATE) for this bank branch and port.",
		"is_default:Check:Default for this Port",
		"column_break_1:Column Break",
		"port_code:Data:Port Code|reqd|list|filter|length=15",
		"port_name:Data:Port Name|ro",
		"bank_section:Section Break:Bank",
		"bank:Link:Bank|opt=Bank|list",
		"bank_account:Link:Bank Account|opt=Bank Account",
		"column_break_2:Column Break",
		"registered_on:Date:Registered On",
		"disabled:Check:Disabled",
	],
	autoname="format:{port_code}-{ad_code}",
	naming_rule="Expression",
	title_field="ad_code",
	search_fields="port_code,bank",
	roles=MANAGER_ONLY,
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
		"export_policy:Select:Export Policy|opt=Free\\nRestricted\\nProhibited\\nSTE|default=Free|filter",
		"import_policy:Select:Import Policy|opt=Free\\nRestricted\\nProhibited\\nSTE|default=Free|filter",
		"column_break_2:Column Break",
		"is_scomet:Check:SCOMET / Dual-use Item",
		"policy_notes:Small Text:Policy Conditions",
		"rates_section:Section Break:Customs Duty Rates",
		"rates:Table:Rates|opt=Customs Tariff Rate",
	],
	autoname="field:tariff_code",
	naming_rule="By fieldname",
	title_field="description",
	search_fields="description,chapter",
	roles=MANAGER_ONLY,
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
		"customs_tariff_item:Link:Tariff Item|opt=Customs Tariff Item|reqd|list|filter",
		"description:Data:Description|fetch=customs_tariff_item.description|ro",
		"schedule_serial_no:Data:Schedule Serial No.|desc=Drawback schedule serial number (DBK Sr. No.) where applicable.",
		"column_break_1:Column Break",
		"rate:Percent:Rate % of FOB|reqd|list",
		"cap_per_unit:Currency:Cap Per Unit (INR)|opt=INR|desc=Leave 0 when the schedule has no per-unit cap.",
		"cap_uom:Link:Cap Unit|opt=UOM|mandatory_depends=eval:doc.cap_per_unit",
		"validity_section:Section Break:Validity",
		"effective_from:Date:Effective From|reqd|list",
		"effective_to:Date:Effective To",
		"column_break_2:Column Break",
		"notification:Data:Notification No.",
	],
	autoname="hash",
	title_field="customs_tariff_item",
	search_fields="scheme,customs_tariff_item",
	roles=MANAGER_ONLY,
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
