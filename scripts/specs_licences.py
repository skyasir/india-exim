"""DGFT authorisations: Advance Authorisation and EPCG (Phase 2)."""

from doctype_gen import doctype

LICENCES = "DGFT Licences"
ROLES = [
	("System Manager", "full"),
	("EXIM Manager", "full"),
	("EXIM User", "write"),
	("Accounts Manager", "read"),
	("Accounts User", "read"),
	("Auditor", "read"),
]
INR = "Company:company:default_currency"
STATUSES = "Active\\nEO Fulfilled\\nEO Period Over\\nRedeemed\\nRegularised\\nCancelled"

doctype(
	"Authorisation Import Item",
	LICENCES,
	[
		"customs_tariff_item:Link:ITC-HS|opt=Customs Tariff Item|reqd|list|width=2",
		"item_code:Link:Item|opt=Item|list|width=2|desc=Optional. Leave empty to allow any item under this ITC-HS code.",
		"description:Small Text:Description",
		"uom:Link:UOM|opt=UOM|list|width=1",
		"column_break_allowed:Column Break",
		"qty_allowed:Float:Qty Allowed|list|width=1",
		"cif_allowed:Currency:CIF Allowed (INR)|opt=" + INR + "|list|width=2",
		"used_section:Section Break:Imported",
		"qty_imported:Float:Qty Imported|ro|nocopy",
		"cif_imported:Currency:CIF Imported (INR)|opt=" + INR + "|ro|nocopy",
		"column_break_used:Column Break",
		"duty_saved:Currency:Duty Saved|opt=" + INR + "|ro|nocopy",
	],
	istable=True,
)

doctype(
	"Authorisation Export Item",
	LICENCES,
	[
		"customs_tariff_item:Link:ITC-HS|opt=Customs Tariff Item|reqd|list|width=2",
		"item_code:Link:Item|opt=Item|list|width=2|desc=Optional. Leave empty to count any item under this ITC-HS code.",
		"description:Small Text:Description",
		"uom:Link:UOM|opt=UOM|list|width=1",
		"column_break_required:Column Break",
		"qty_required:Float:Qty to Export|list|width=1",
		"fob_required:Currency:FOB Required (INR)|opt=" + INR + "|list|width=2",
		"done_section:Section Break:Exported",
		"qty_exported:Float:Qty Exported|ro|nocopy",
		"column_break_done:Column Break",
		"fob_exported:Currency:FOB Exported (INR)|opt=" + INR + "|ro|nocopy",
	],
	istable=True,
)

doctype(
	"Export Authorisation",
	LICENCES,
	[
		"naming_series:Select:Series|opt=EAU-.YYYY.-.#####|reqd|default=EAU-.YYYY.-.#####|phide",
		"scheme:Select:Scheme|opt=Advance Authorisation\\nEPCG|reqd|list|filter|default=Advance Authorisation",
		"company:Link:Company|opt=Company|reqd|filter",
		"authorisation_number:Data:Authorisation No.|reqd|list|unique|search",
		"authorisation_date:Date:Authorisation Date|reqd|list",
		"column_break_head:Column Break",
		"status:Select:Status|opt=" + STATUSES + "|default=Active|ro|list|filter|bold|nocopy",
		"port_of_registration:Data:Port of Registration (Port Code)|length=6",
		"file_number:Data:DGFT File No.",
		"periods_section:Section Break:Validity and Export Obligation Period",
		"import_validity_upto:Date:Import Valid Upto|desc=Advance Authorisation: 12 months from issue; EPCG: 24 months. Set from the authorisation date when empty; enter the date on the licence if it differs.",
		"column_break_periods:Column Break",
		"eo_period_upto:Date:Export Obligation Period Ends|desc=Advance Authorisation: 18 months from issue; EPCG: 6 years. Extend here when DGFT allows an extension.",
		"aa_section:Section Break:Advance Authorisation|depends=eval:doc.scheme=='Advance Authorisation'",
		"sion_reference:Data:SION / Norms|desc=Standard Input Output Norm serial number, or 'Self-declared' with the norms ratification reference.",
		"column_break_aa:Column Break",
		"value_addition_percent:Percent:Minimum Value Addition %|default=15",
		"epcg_section:Section Break:EPCG|depends=eval:doc.scheme=='EPCG'",
		"eo_multiple:Float:EO Multiple of Duty Saved|default=6|desc=Export obligation as a multiple of the duty and taxes saved on the capital goods (6 under the Foreign Trade Policy; less for some categories).",
		"block_1_percent:Percent:Block 1 EO %|default=50",
		"column_break_epcg:Column Break",
		"block_1_upto:Date:Block 1 Ends|desc=4 years from issue unless DGFT says otherwise.",
		"installation_certificate_date:Date:Installation Certificate Date",
		"average_eo:Currency:Average Export Obligation (INR, per year)|opt="
		+ INR
		+ "|desc=Average exports to be kept up in addition to the specific obligation, when the authorisation sets one.",
		"incentives_section:Section Break:Incentives on Exports Under This Authorisation|desc=Whether Duty Drawback and RoDTEP may be claimed on shipping bills that discharge this obligation. Check the current Foreign Trade Policy and RoDTEP notification; the rule has changed over time.",
		"drawback_admissible:Check:Duty Drawback Admissible",
		"column_break_incentives:Column Break",
		"rodtep_admissible:Check:RoDTEP Admissible",
		"imports_section:Section Break:Imports Allowed",
		"imports:Table:Imports|opt=Authorisation Import Item",
		"exports_section:Section Break:Export Obligation",
		"exports:Table:Exports|opt=Authorisation Export Item|desc=Advance Authorisation: the products and FOB value to export. EPCG: the products whose exports count towards the obligation; the FOB required is worked out from the duty saved.",
		"totals_section:Section Break:Position",
		"total_cif_allowed:Currency:CIF Allowed|opt=" + INR + "|ro",
		"total_cif_imported:Currency:CIF Imported|opt=" + INR + "|ro|nocopy",
		"total_duty_saved:Currency:Duty Saved|opt=" + INR + "|ro|nocopy",
		"column_break_totals:Column Break",
		"eo_required:Currency:Export Obligation (FOB INR)|opt=" + INR + "|ro|bold",
		"eo_fulfilled:Currency:EO Fulfilled (FOB INR)|opt=" + INR + "|ro|nocopy",
		"eo_balance:Currency:EO Balance|opt=" + INR + "|ro|nocopy",
		"eo_percent:Percent:EO Fulfilled %|ro|list|nocopy",
		"redemption_section:Section Break:Redemption",
		"eodc_number:Data:EODC / Redemption Letter No.",
		"eodc_date:Date:EODC Date",
		"column_break_redemption:Column Break",
		"regularisation_reference:Data:Regularisation Reference|desc=When the obligation was not met and duty with interest was paid to regularise.",
		"is_cancelled:Check:Authorisation Cancelled / Surrendered",
		"remarks:Small Text:Remarks",
	],
	autoname="naming_series:",
	title_field="authorisation_number",
	search_fields="authorisation_number,scheme,status",
	roles=ROLES,
	links=[
		{
			"group": "Customs",
			"link_doctype": "Bill of Entry Item",
			"link_fieldname": "exim_authorisation",
			"parent_doctype": "Bill of Entry",
			"is_child_table": 1,
			"table_fieldname": "items",
		},
		{"group": "Customs", "link_doctype": "Shipping Bill", "link_fieldname": "export_authorisation"},
	],
)
