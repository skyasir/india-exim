"""Custom fields India EXIM adds to ERPNext and India Compliance doctypes."""

from india_exim.features import when
from india_exim.setup.accounts import EXIM_ACCOUNTS

# link_filters of a Link to Port Master: Indian customs ports, or ports abroad
INDIAN_PORTS = '[["Port Master","port_country","=","India"],["Port Master","disabled","=",0]]'
FOREIGN_PORTS = '[["Port Master","port_country","!=","India"],["Port Master","disabled","=",0]]'

STATUS_HOLDER_OPTIONS = "\nOne Star Export House\nTwo Star Export House\nThree Star Export House\nFour Star Export House\nFive Star Export House"


def get_company_fields():
	fields = [
		{
			"fieldname": "exim_tab",
			"fieldtype": "Tab Break",
			"label": "Export & Import",
			"insert_after": "default_scrap_warehouse",
		},
		{
			"fieldname": "exim_registration_section",
			"fieldtype": "Section Break",
			"label": "Foreign Trade Registration",
			"insert_after": "exim_tab",
		},
		{
			"fieldname": "exim_iec",
			"fieldtype": "Data",
			"label": "Importer-Exporter Code (IEC)",
			"length": 10,
			"insert_after": "exim_registration_section",
			"description": "10-character IEC issued by DGFT (same as the company PAN).",
		},
		{
			"fieldname": "exim_status_holder",
			"fieldtype": "Select",
			"label": "Status Holder Category",
			"options": STATUS_HOLDER_OPTIONS,
			"insert_after": "exim_iec",
			"depends_on": when("exports", "exim_status_holder"),
		},
		{
			"fieldname": "exim_ecgc_policy_number",
			"fieldtype": "Data",
			"label": "ECGC Policy No.",
			"depends_on": when("ecgc", "exim_ecgc_policy_number"),
			"insert_after": "exim_status_holder",
		},
		{
			"fieldname": "exim_registration_column",
			"fieldtype": "Column Break",
			"insert_after": "exim_ecgc_policy_number",
		},
		{
			"fieldname": "exim_rcmc_number",
			"fieldtype": "Data",
			"label": "RCMC No.",
			"insert_after": "exim_registration_column",
			"depends_on": when("exports", "exim_rcmc_number"),
		},
		{
			"fieldname": "exim_rcmc_council",
			"fieldtype": "Data",
			"label": "Export Promotion Council",
			"insert_after": "exim_rcmc_number",
			"depends_on": when("exports", "exim_rcmc_council"),
		},
		{
			"fieldname": "exim_rcmc_valid_upto",
			"fieldtype": "Date",
			"label": "RCMC Valid Upto",
			"insert_after": "exim_rcmc_council",
			"depends_on": when("exports", "exim_rcmc_valid_upto"),
		},
	]

	previous = "exim_rcmc_valid_upto"
	for section, description in (
		("Export", "Export incentives, refunds and export-side charges."),
		(
			"Import",
			"Customs duty expense and payable accounts are India Compliance's Default Customs Duty"
			" accounts on the Accounts tab and are used as they are.",
		),
	):
		section_field = f"exim_{section.lower()}_accounts_section"
		fields.append(
			{
				"fieldname": section_field,
				"fieldtype": "Section Break",
				"label": f"{section} Accounts",
				"collapsible": 1,
				"description": description,
				"insert_after": previous,
				# set up by India EXIM for every company, so only the business type hides them
				"depends_on": when(f"{section.lower()}s"),
			}
		)
		previous = section_field
		section_accounts = [name for name, spec in EXIM_ACCOUNTS.items() if spec["section"] == section]
		split_at = (len(section_accounts) + 1) // 2
		for index, fieldname in enumerate(section_accounts):
			if index == split_at:
				column = f"exim_{section.lower()}_accounts_column"
				fields.append({"fieldname": column, "fieldtype": "Column Break", "insert_after": previous})
				previous = column
			fields.append(
				{
					"fieldname": fieldname,
					"fieldtype": "Link",
					"label": EXIM_ACCOUNTS[fieldname]["label"],
					"options": "Account",
					"insert_after": previous,
				}
			)
			previous = fieldname

	fields += [
		{
			"fieldname": "exim_common_section",
			"fieldtype": "Section Break",
			"label": "Cost Center and Exchange Difference",
			"collapsible": 1,
			"insert_after": previous,
		},
		{
			"fieldname": "exim_cost_center",
			"fieldtype": "Link",
			"label": "EXIM Cost Center",
			"options": "Cost Center",
			"insert_after": "exim_common_section",
		},
		{
			"fieldname": "exim_common_column",
			"fieldtype": "Column Break",
			"insert_after": "exim_cost_center",
		},
		{
			"fieldname": "exim_forex_gain_loss_account",
			"fieldtype": "Link",
			"label": "Forex Gain / Loss on Realisation",
			"options": "Account",
			"insert_after": "exim_common_column",
			"description": "Leave empty to use the company's Exchange Gain / Loss account.",
		},
	]
	return fields


def chain(fields: list[dict], first_insert_after: str) -> list[dict]:
	"""Give each field insert_after = the previous field, so a block keeps its order."""
	previous = first_insert_after
	for field in fields:
		field.setdefault("insert_after", previous)
		previous = field["fieldname"]
	return fields


IMDG_CLASSES = (
	"\n1 - Explosives\n2.1 - Flammable Gases\n2.2 - Non-flammable Gases\n2.3 - Toxic Gases"
	"\n3 - Flammable Liquids\n4.1 - Flammable Solids\n4.2 - Spontaneously Combustible"
	"\n4.3 - Dangerous When Wet\n5.1 - Oxidizers\n5.2 - Organic Peroxides\n6.1 - Toxic Substances"
	"\n6.2 - Infectious Substances\n7 - Radioactive\n8 - Corrosives\n9 - Miscellaneous"
)


def get_item_fields() -> list[dict]:
	"""The Export & Import tab, after the Purchasing tab. Frappe adds a custom tab after the whole
	tab its insert_after is in, so ERPNext's Foreign Trade Details (Country of Origin, Customs
	Tariff Number) stays in Purchasing. Rates and trade policy stay on the Customs Tariff Item and
	are only shown here, since the law sets them per tariff code."""
	tab = {
		"fieldname": "exim_tab",
		"fieldtype": "Tab Break",
		"label": "Export & Import",
		"insert_after": "customs_tariff_number",
	}
	fields = [
		{
			"fieldname": "exim_classification_section",
			"fieldtype": "Section Break",
			"label": "Customs Classification",
		},
		{
			"fieldname": "exim_customs_tariff_item",
			"fieldtype": "Link",
			"label": "ITC-HS Code",
			"options": "Customs Tariff Item",
		},
		# the law's unit for the code; asked about only when it is not the stock unit
		{
			"fieldname": "exim_uqc",
			"fieldtype": "Link",
			"label": "Customs Unit (UQC)",
			"options": "UOM",
			"fetch_from": "exim_customs_tariff_item.uqc",
			"read_only": 1,
			"hidden": 1,
		},
		{
			"fieldname": "exim_uqc_conversion_factor",
			"fieldtype": "Float",
			"label": "UQC per Stock Unit",
			"depends_on": "eval:doc.exim_uqc && doc.exim_uqc != doc.stock_uom",
			"description": "How many customs units one stock unit is, e.g. 12 when 1 Box = 12 KGS.",
		},
		{"fieldname": "exim_classification_column", "fieldtype": "Column Break"},
		{"fieldname": "exim_tariff_summary", "fieldtype": "HTML", "label": "Tariff Summary"},
		{
			"fieldname": "exim_incentives_section",
			"fieldtype": "Section Break",
			"label": "Export Incentives",
			"hide_border": 1,
			"depends_on": when("incentives"),
		},
		{"fieldname": "exim_incentive_rates", "fieldtype": "HTML", "label": "Incentive Rates"},
		{
			"fieldname": "exim_claims_section",
			"fieldtype": "Section Break",
			"depends_on": when("incentives"),
		},
		{
			"fieldname": "exim_claim_drawback",
			"fieldtype": "Check",
			"label": "Claim Duty Drawback",
			"default": "1",
		},
		{
			"fieldname": "exim_drawback_serial_no",
			"fieldtype": "Autocomplete",
			"label": "Drawback Schedule Serial No.",
			"depends_on": "exim_claim_drawback",
			"description": "This code has more than one drawback entry; pick the one for this item.",
		},
		{"fieldname": "exim_incentives_column", "fieldtype": "Column Break"},
		{
			"fieldname": "exim_claim_rodtep",
			"fieldtype": "Check",
			"label": "Claim RoDTEP",
			"default": "1",
		},
		{
			"fieldname": "exim_claim_rosctl",
			"fieldtype": "Check",
			"label": "Claim RoSCTL",
			"default": "1",
			"depends_on": "eval:['61', '62', '63'].includes((doc.exim_customs_tariff_item || '').slice(0, 2))",
		},
		{
			"fieldname": "exim_duty_section",
			"fieldtype": "Section Break",
			"label": "Import Duty",
			"depends_on": when("imports"),
		},
		{"fieldname": "exim_duty_rates", "fieldtype": "HTML", "label": "Import Duty Rates"},
		{
			"fieldname": "exim_packing_section",
			"fieldtype": "Section Break",
			"label": "Packing and Printed Description",
			"collapsible": 1,
			"collapsible_depends_on": "eval:doc.exim_gross_weight_per_unit || doc.exim_units_per_package || doc.exim_customs_description",
			"depends_on": when(
				"exports", "exim_gross_weight_per_unit", "exim_units_per_package", "exim_customs_description"
			),
		},
		{
			"fieldname": "exim_gross_weight_per_unit",
			"fieldtype": "Float",
			"label": "Gross Weight Per Unit",
			"description": "Packing included, in the Weight UOM of the Inventory tab.",
		},
		{"fieldname": "exim_units_per_package", "fieldtype": "Float", "label": "Stock Units per Package"},
		{
			"fieldname": "exim_package_type",
			"fieldtype": "Data",
			"label": "Package Type",
			"placeholder": "Carton, Bag, Drum, Pallet",
		},
		{"fieldname": "exim_packing_column", "fieldtype": "Column Break"},
		{"fieldname": "exim_package_length", "fieldtype": "Float", "label": "Length (cm)"},
		{"fieldname": "exim_package_width", "fieldtype": "Float", "label": "Width (cm)"},
		{"fieldname": "exim_package_height", "fieldtype": "Float", "label": "Height (cm)"},
		{"fieldname": "exim_description_column", "fieldtype": "Column Break"},
		{
			"fieldname": "exim_package_volume",
			"fieldtype": "Float",
			"label": "Volume (CBM)",
			"read_only": 1,
			"precision": "4",
		},
		{
			"fieldname": "exim_customs_description",
			"fieldtype": "Small Text",
			"label": "Description for Customs",
			"description": "Printed on the export invoice and packing list instead of the item description.",
		},
		{
			"fieldname": "exim_handling_section",
			"fieldtype": "Section Break",
			"label": "Dangerous Goods and Handling",
			"depends_on": when("special_cargo", "exim_is_dangerous_goods", "exim_is_reefer"),
			"collapsible": 1,
			"collapsible_depends_on": "eval:doc.exim_is_dangerous_goods || doc.exim_is_reefer",
		},
		{"fieldname": "exim_is_dangerous_goods", "fieldtype": "Check", "label": "Dangerous Goods"},
		{
			"fieldname": "exim_un_number",
			"fieldtype": "Data",
			"label": "UN Number",
			"depends_on": "exim_is_dangerous_goods",
			"mandatory_depends_on": "exim_is_dangerous_goods",
		},
		{
			"fieldname": "exim_imdg_class",
			"fieldtype": "Select",
			"label": "IMDG Class",
			"options": IMDG_CLASSES,
			"depends_on": "exim_is_dangerous_goods",
			"mandatory_depends_on": "exim_is_dangerous_goods",
		},
		{
			"fieldname": "exim_packing_group",
			"fieldtype": "Select",
			"label": "Packing Group",
			"options": "\nI\nII\nIII",
			"depends_on": "exim_is_dangerous_goods",
		},
		{"fieldname": "exim_handling_column", "fieldtype": "Column Break"},
		{"fieldname": "exim_is_reefer", "fieldtype": "Check", "label": "Needs Temperature Control"},
		{
			"fieldname": "exim_temperature_setting",
			"fieldtype": "Data",
			"label": "Temperature Setting",
			"depends_on": "exim_is_reefer",
			"description": "e.g. +2 to +8 °C",
		},
		{
			"fieldname": "exim_licences_section",
			"fieldtype": "Section Break",
			"label": "DGFT Licences",
			"collapsible": 1,
			"collapsible_depends_on": "exim_sion_reference",
			"depends_on": when("licences", "exim_sion_reference"),
		},
		{
			"fieldname": "exim_sion_reference",
			"fieldtype": "Data",
			"label": "SION / Norms Reference",
			"description": "Standard Input Output Norm used for Advance Authorisations.",
		},
	]
	return [tab, *chain(fields, "exim_tab")]


CUSTOM_FIELDS = {
	"Company": get_company_fields(),
	"Item": get_item_fields(),
	"Journal Entry": [
		{
			"fieldname": "exim_reference_type",
			"fieldtype": "Link",
			"label": "EXIM Reference Type",
			"options": "DocType",
			"insert_after": "user_remark",
			"read_only": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "exim_reference_name",
			"fieldtype": "Dynamic Link",
			"label": "EXIM Reference",
			"options": "exim_reference_type",
			"insert_after": "exim_reference_type",
			"read_only": 1,
			"no_copy": 1,
			"search_index": 1,
		},
	],
	"Sales Invoice": [
		{
			"fieldname": "exim_lut",
			"fieldtype": "Link",
			"label": "Letter of Undertaking",
			"options": "Letter of Undertaking",
			"insert_after": "shipping_bill_date",
			"read_only": 1,
			"no_copy": 1,
			"depends_on": "eval:doc.exim_lut",
			"description": "Set automatically for zero-rated exports without IGST.",
		},
	],
}


SHOW_EXPORT = "exim_is_export"
SHOW_IMPORT = "exim_is_import"
EXPORT_TAB = "Export Details"
IMPORT_TAB = "Import Details"


def flag(
	fieldname: str, label: str, insert_after: str, fetch_from: str | None = None, description: str = ""
) -> dict:
	"""The tick that shows the Export / Import Details tab. Kept outside the tab, and shown when the
	Business Type includes that side (or the tick is already set)."""
	field = {
		"fieldname": fieldname,
		"fieldtype": "Check",
		"label": label,
		"insert_after": insert_after,
		"in_standard_filter": 1,
		"description": description,
		"depends_on": when("exports" if fieldname == SHOW_EXPORT else "imports", fieldname),
	}
	if fetch_from:
		field.update({"fetch_from": fetch_from, "fetch_if_empty": 1})
	return field


PAYMENT_TERMS = "\nAdvance\nLetter of Credit\nDocuments against Payment (DP)\nDocuments against Acceptance (DA)\nOpen Account"
MODES = "\nSea FCL\nSea LCL\nAir\nCourier\nRoad\nRail"


def get_party_fields() -> list[dict]:
	"""Consignee | Buyer | Notify Party side by side: pick a Customer, then one of
	its Addresses and Contacts. The text under each link is filled from it
	(india_exim/utils/parties.py) and is what prints."""
	fields = [
		{
			"fieldname": "exim_parties_section",
			"fieldtype": "Section Break",
			"label": "Different Consignee, Buyer or Notify Party",
			"collapsible": 1,
			"collapsible_depends_on": "eval:doc.exim_consignee || doc.exim_buyer || doc.exim_notify",
		}
	]
	for index, (party, label) in enumerate(
		(("consignee", "Consignee"), ("buyer", "Buyer"), ("notify", "Notify Party"))
	):
		if index:
			fields.append({"fieldname": f"exim_{party}_column", "fieldtype": "Column Break"})
		fields += [
			{
				"fieldname": f"exim_{party}",
				"fieldtype": "Link",
				"label": label,
				"options": "Customer",
				"allow_on_submit": 1,
			},
			{
				"fieldname": f"exim_{party}_address",
				"fieldtype": "Link",
				"label": f"{label} Address",
				"options": "Address",
				"allow_on_submit": 1,
			},
			{
				"fieldname": f"exim_{party}_address_display",
				"fieldtype": "Small Text",
				"label": "Address",
				"read_only": 1,
				"allow_on_submit": 1,
			},
			{
				"fieldname": f"exim_{party}_contact",
				"fieldtype": "Link",
				"label": f"{label} Contact",
				"options": "Contact",
				"allow_on_submit": 1,
			},
			{
				"fieldname": f"exim_{party}_contact_display",
				"fieldtype": "Small Text",
				"label": "Contact",
				"read_only": 1,
				"allow_on_submit": 1,
			},
		]
	return fields


def get_order_and_invoice_fields(
	insert_after: str, include_summary: bool, include_port_of_loading: bool = False
) -> list[dict]:
	"""Same fieldnames on Sales Order and Sales Invoice so ERPNext's mapper copies them.

	Delivery Note and Sales Invoice already have India Compliance's Port Code, so the port of
	loading is only added to Quotation and Sales Order and is copied into Port Code from there."""
	fields = [
		{"fieldname": "exim_tab", "fieldtype": "Tab Break", "label": EXPORT_TAB, "depends_on": SHOW_EXPORT},
	]
	if include_summary:
		fields += [
			{"fieldname": "exim_summary_section", "fieldtype": "Section Break", "label": "Export Status"},
			{"fieldname": "exim_summary", "fieldtype": "HTML", "label": "Export Status"},
		]
	lc = "eval:doc.exim_payment_terms_type == 'Letter of Credit'"
	# what every export needs, first and open; the rest stays closed until it is used
	fields += [
		{"fieldname": "exim_route_section", "fieldtype": "Section Break", "label": "Route and Terms"},
		*(
			[
				{
					"fieldname": "exim_port_of_loading",
					"fieldtype": "Link",
					"label": "Port of Loading",
					"options": "Port Master",
					"link_filters": INDIAN_PORTS,
					"ignore_user_permissions": 1,
					"description": "Becomes the Port Code on the delivery note and invoice.",
				}
			]
			if include_port_of_loading
			else []
		),
		{
			"fieldname": "exim_destination_country",
			"fieldtype": "Link",
			"label": "Destination Country",
			"options": "Country",
			"ignore_user_permissions": 1,
		},
		{
			"fieldname": "exim_port_of_discharge",
			"fieldtype": "Link",
			"label": "Port of Discharge",
			"options": "Port Master",
			"link_filters": FOREIGN_PORTS,
			"ignore_user_permissions": 1,
		},
		{"fieldname": "exim_route_column", "fieldtype": "Column Break"},
		{"fieldname": "exim_mode_of_transport", "fieldtype": "Select", "label": "Mode", "options": MODES},
		{
			"fieldname": "exim_payment_terms_type",
			"fieldtype": "Select",
			"label": "Export Payment Terms",
			"options": PAYMENT_TERMS,
		},
		{"fieldname": "exim_lc_number", "fieldtype": "Data", "label": "LC No.", "depends_on": lc},
		{"fieldname": "exim_lc_date", "fieldtype": "Date", "label": "LC Date", "depends_on": lc},
		{
			"fieldname": "exim_latest_shipment_date",
			"fieldtype": "Date",
			"label": "Latest Shipment Date",
			"depends_on": lc,
		},
		{
			"fieldname": "exim_value_section",
			"fieldtype": "Section Break",
			"label": "Freight and Insurance in the Price",
			"depends_on": "eval:(doc.incoterm && !['EXW', 'FCA', 'FAS', 'FOB'].includes(doc.incoterm)) || doc.exim_freight || doc.exim_insurance",
			"description": "Deducted to arrive at the FOB value on the shipping bill.",
		},
		{"fieldname": "exim_freight", "fieldtype": "Currency", "label": "Freight", "options": "currency"},
		{"fieldname": "exim_value_column", "fieldtype": "Column Break"},
		{"fieldname": "exim_insurance", "fieldtype": "Currency", "label": "Insurance", "options": "currency"},
	]
	fields += get_party_fields()
	fields += [
		{
			"fieldname": "exim_marks_section",
			"fieldtype": "Section Break",
			"label": "More Transport Details",
			"collapsible": 1,
			"collapsible_depends_on": "eval:doc.exim_final_destination || doc.exim_pre_carriage_by || doc.exim_place_of_receipt || doc.exim_marks_and_numbers",
		},
		{"fieldname": "exim_final_destination", "fieldtype": "Data", "label": "Final Destination"},
		{"fieldname": "exim_pre_carriage_by", "fieldtype": "Data", "label": "Pre-carriage By"},
		{
			"fieldname": "exim_place_of_receipt",
			"fieldtype": "Data",
			"label": "Place of Receipt by Pre-carrier",
		},
		{"fieldname": "exim_marks_column", "fieldtype": "Column Break"},
		{"fieldname": "exim_marks_and_numbers", "fieldtype": "Small Text", "label": "Marks and Numbers"},
	]
	return chain(fields, insert_after)


CUSTOM_FIELDS["Customer"] = [
	flag(
		"exim_is_export",
		"Export Customer",
		"customer_type",
		description="Overseas buyer. Shows the Export Details tab and is copied to orders and invoices.",
	)
] + chain(
	[
		{"fieldname": "exim_tab", "fieldtype": "Tab Break", "label": EXPORT_TAB, "depends_on": SHOW_EXPORT},
		{
			"fieldname": "exim_documents_section",
			"fieldtype": "Section Break",
			"label": "Buyer Document Instructions",
		},
		{
			"fieldname": "exim_marking_instructions",
			"fieldtype": "Small Text",
			"label": "Labelling and Marking Instructions",
		},
		{
			"fieldname": "exim_document_instructions",
			"fieldtype": "Text Editor",
			"label": "Other Document Instructions",
		},
		{
			"fieldname": "exim_screening_section",
			"fieldtype": "Section Break",
			"label": "Screening and Credit Cover",
			"description": "Record each check of this buyer against denied-party and sanctions lists. Export orders warn or stop when it is missing, old or a match (India EXIM Settings > Pre-shipment Controls).",
		},
		{"fieldname": "exim_screened_on", "fieldtype": "Date", "label": "Denied-party Screening Done On"},
		{
			"fieldname": "exim_screening_result",
			"fieldtype": "Select",
			"label": "Screening Result",
			"options": "\nClear\nPossible Match - Cleared on Review\nMatch - Do Not Trade",
		},
		{"fieldname": "exim_screening_reference", "fieldtype": "Data", "label": "Lists Checked / Reference"},
		{"fieldname": "exim_screening_column", "fieldtype": "Column Break"},
		{
			"fieldname": "exim_ecgc_buyer_limit",
			"fieldtype": "Currency",
			"label": "ECGC Buyer Limit (INR)",
			"depends_on": when("ecgc", "exim_ecgc_buyer_limit"),
			"description": "Credit limit approved by ECGC for this buyer. Export orders warn when the amount owed would exceed it.",
		},
		{
			"fieldname": "exim_ecgc_limit_valid_upto",
			"fieldtype": "Date",
			"label": "ECGC Limit Valid Upto",
			"depends_on": when("ecgc", "exim_ecgc_limit_valid_upto"),
		},
	],
	"supplier_numbers",
)

CUSTOM_FIELDS["Country"] = chain(
	[
		{
			"fieldname": "exim_section",
			"fieldtype": "Section Break",
			"label": "Export Controls",
			"description": "Used by India EXIM's pre-shipment checks on export quotations, orders and invoices.",
		},
		{
			"fieldname": "exim_trade_risk",
			"fieldtype": "Select",
			"label": "Trade Risk",
			"options": "\nSanctioned\nRestricted\nPayment Risk",
			"description": "Sanctioned: exports are stopped (or warned, per settings). Restricted and Payment Risk: a warning.",
		},
		{
			"fieldname": "exim_requires_legalisation",
			"fieldtype": "Check",
			"label": "Documents Need Legalisation",
		},
		{"fieldname": "exim_column", "fieldtype": "Column Break"},
		{"fieldname": "exim_trade_risk_note", "fieldtype": "Small Text", "label": "Notes"},
	],
	"time_zones",
)

CUSTOM_FIELDS["Supplier"] = [
	flag(
		"exim_is_import",
		"Import Supplier",
		"supplier_type",
		description="Overseas supplier. Shows the Import Details tab and is copied to purchase invoices.",
	)
] + chain(
	[
		{"fieldname": "exim_tab", "fieldtype": "Tab Break", "label": IMPORT_TAB, "depends_on": SHOW_IMPORT},
		{
			"fieldname": "exim_origin_section",
			"fieldtype": "Section Break",
			"label": "Origin and Trade Agreement",
		},
		{
			"fieldname": "exim_fta_eligible",
			"fieldtype": "Check",
			"label": "Supplies Eligible for FTA Concession",
		},
		{
			"fieldname": "exim_trade_agreement",
			"fieldtype": "Data",
			"label": "Trade Agreement",
			"depends_on": "exim_fta_eligible",
			"description": "e.g. India-UAE CEPA, India-ASEAN TIG.",
		},
	],
	"customer_numbers",
)

# Quotation -> Sales Order -> Delivery Note -> Sales Invoice: the same fieldnames on all of them, so ERPNext's
# mappers carry the export details forward. A quotation's party can be a Lead, so the tick is
# fetched from the customer in india_exim.overrides.quotation rather than by fetch_from.
CUSTOM_FIELDS["Quotation"] = [
	flag("exim_is_export", "Is Export", "order_type")
] + get_order_and_invoice_fields("supplier_quotation", include_summary=False, include_port_of_loading=True)
CUSTOM_FIELDS["Sales Order"] = [
	flag("exim_is_export", "Is Export", "is_subcontracted", fetch_from="customer.exim_is_export")
] + get_order_and_invoice_fields("proforma_html", include_summary=False, include_port_of_loading=True)
CUSTOM_FIELDS["Delivery Note"] = [
	flag("exim_is_export", "Is Export", "is_export_with_gst", fetch_from="customer.exim_is_export")
] + get_order_and_invoice_fields("instructions", include_summary=False)
CUSTOM_FIELDS["Sales Invoice"] = (
	CUSTOM_FIELDS["Sales Invoice"]
	+ [flag("exim_is_export", "Is Export", "is_export_with_gst", fetch_from="customer.exim_is_export")]
	+ get_order_and_invoice_fields("is_discounted", include_summary=True)
)

MERCHANT_EXPORT = "exim_merchant_export"
CUSTOM_FIELDS["Purchase Invoice"] = [
	flag("exim_is_import", "Is Import", "is_reverse_charge", fetch_from="supplier.exim_is_import"),
	*chain(
		[
			{
				"fieldname": MERCHANT_EXPORT,
				"fieldtype": "Check",
				"label": "Bought for Merchant Export (0.1% GST)",
				"depends_on": "eval:!doc.exim_is_import && (frappe.boot.exim_features?.merchant_export || doc.exim_merchant_export)",
				"description": "Goods bought from an Indian supplier at the concessional 0.1% GST for export by us as a merchant exporter.",
			},
			{
				"fieldname": "exim_merchant_export_due",
				"fieldtype": "Date",
				"label": "Export By",
				"read_only": 1,
				"depends_on": MERCHANT_EXPORT,
				"description": "The goods must be exported within 90 days of the supplier's invoice (set in India EXIM Settings).",
			},
			{
				"fieldname": "exim_merchant_shipping_bill",
				"fieldtype": "Link",
				"label": "Exported Under Shipping Bill",
				"options": "Shipping Bill",
				"allow_on_submit": 1,
				"depends_on": MERCHANT_EXPORT,
			},
			{
				"fieldname": "exim_merchant_proof_sent_on",
				"fieldtype": "Date",
				"label": "Shipping Bill and EGM Copy Sent to Supplier On",
				"allow_on_submit": 1,
				"depends_on": MERCHANT_EXPORT,
			},
		],
		"exim_is_import",
	),
] + chain(
	[
		{"fieldname": "exim_tab", "fieldtype": "Tab Break", "label": IMPORT_TAB, "depends_on": SHOW_IMPORT},
		{
			"fieldname": "exim_import_shipment",
			"fieldtype": "Link",
			"label": "Import Shipment",
			"options": "Import Shipment",
			"read_only": 1,
			"no_copy": 1,
			"allow_on_submit": 1,
			"description": "Transport details below follow the shipment.",
		},
		{"fieldname": "exim_origin_section", "fieldtype": "Section Break", "label": "Origin"},
		{
			"fieldname": "exim_origin_country",
			"fieldtype": "Link",
			"label": "Country of Origin",
			"options": "Country",
			"ignore_user_permissions": 1,
		},
		{"fieldname": "exim_fta_claimed", "fieldtype": "Check", "label": "FTA Concession to be Claimed"},
		{
			"fieldname": "exim_certificate_of_origin",
			"fieldtype": "Data",
			"label": "Certificate of Origin No.",
			"depends_on": "exim_fta_claimed",
		},
		{"fieldname": "exim_origin_column", "fieldtype": "Column Break"},
		{
			"fieldname": "exim_port_of_loading",
			"fieldtype": "Link",
			"label": "Port of Loading",
			"options": "Port Master",
			"link_filters": FOREIGN_PORTS,
			"ignore_user_permissions": 1,
		},
		{
			"fieldname": "exim_port_of_discharge",
			"fieldtype": "Link",
			"label": "Port of Discharge",
			"options": "Port Master",
			"link_filters": INDIAN_PORTS,
			"ignore_user_permissions": 1,
		},
		{
			"fieldname": "exim_cha",
			"fieldtype": "Link",
			"label": "Customs Broker (CHA)",
			"options": "Supplier",
		},
		{
			"fieldname": "exim_transport_section",
			"fieldtype": "Section Break",
			"label": "Transport and Arrival",
		},
		{"fieldname": "exim_bl_number", "fieldtype": "Data", "label": "BL / AWB No.", "allow_on_submit": 1},
		{"fieldname": "exim_bl_date", "fieldtype": "Date", "label": "BL / AWB Date", "allow_on_submit": 1},
		{"fieldname": "exim_igm_number", "fieldtype": "Data", "label": "IGM No.", "allow_on_submit": 1},
		{"fieldname": "exim_igm_date", "fieldtype": "Date", "label": "IGM Date", "allow_on_submit": 1},
		{"fieldname": "exim_transport_column", "fieldtype": "Column Break"},
		{"fieldname": "exim_eta", "fieldtype": "Date", "label": "ETA", "allow_on_submit": 1},
		{"fieldname": "exim_ata", "fieldtype": "Date", "label": "Actual Arrival", "allow_on_submit": 1},
		{
			"fieldname": "exim_free_days",
			"fieldtype": "Int",
			"label": "Free Days (Detention / Demurrage)",
			"allow_on_submit": 1,
		},
		{
			"fieldname": "exim_free_time_ends",
			"fieldtype": "Date",
			"label": "Free Time Ends",
			"read_only": 1,
			"allow_on_submit": 1,
		},
	],
	"remarks",
)

CUSTOM_FIELDS["Payment Entry"] = chain(
	[
		{
			"fieldname": "exim_section",
			"fieldtype": "Section Break",
			"label": "Foreign Remittance (FEMA)",
			"collapsible": 1,
			"depends_on": "eval:['Customer', 'Supplier'].includes(doc.party_type)",
			"description": "Use Reference No. for the IRM / FIRC (receipts) or ORM (payments) number and Deductions for bank charges.",
		},
		{
			"fieldname": "exim_purpose_code",
			"fieldtype": "Data",
			"label": "RBI Purpose Code",
			"length": 10,
			"allow_on_submit": 1,
		},
		{
			"fieldname": "exim_ebrc_number",
			"fieldtype": "Data",
			"label": "e-BRC No.",
			"allow_on_submit": 1,
			"depends_on": "eval:doc.payment_type == 'Receive'",
			"description": "Electronic Bank Realisation Certificate, once issued on the DGFT portal.",
		},
		{
			"fieldname": "exim_ebrc_date",
			"fieldtype": "Date",
			"label": "e-BRC Date",
			"allow_on_submit": 1,
			"depends_on": "eval:doc.payment_type == 'Receive'",
		},
		{"fieldname": "exim_column", "fieldtype": "Column Break"},
		{
			"fieldname": "exim_15ca_acknowledgement",
			"fieldtype": "Data",
			"label": "Form 15CA Acknowledgement",
			"depends_on": "eval:doc.payment_type == 'Pay'",
		},
		{
			"fieldname": "exim_15cb_reference",
			"fieldtype": "Data",
			"label": "Form 15CB Reference",
			"depends_on": "eval:doc.payment_type == 'Pay'",
		},
	],
	"remarks",
)

CUSTOM_FIELDS["Bill of Entry"] = chain(
	[
		{
			"fieldname": "exim_duty_section",
			"fieldtype": "Section Break",
			"label": "Customs Duty Calculation",
		},
		{
			"fieldname": "exim_calculate_duty",
			"fieldtype": "Check",
			"label": "Calculate Duty from Customs Tariff",
			"default": "1",
			"description": "Assessable value at the CBIC import exchange rate and BCD / SWS / AIDC from the tariff rates in force on the Bill of Entry date.",
		},
		{
			"fieldname": "exim_be_type",
			"fieldtype": "Select",
			"label": "Bill of Entry Type",
			"options": "Home Consumption\nWarehousing\nEx-Bond",
			"default": "Home Consumption",
		},
		{
			"fieldname": "exim_authorisation",
			"fieldtype": "Link",
			"label": "Import Under Authorisation",
			"depends_on": when("licences", "exim_authorisation"),
			"options": "Export Authorisation",
			"description": "Advance Authorisation or EPCG. Customs duty is then recorded as duty foregone instead of payable, and the import is debited to the authorisation. Fills every row; leave it empty to pick a licence on some rows only.",
		},
		{
			"fieldname": "exim_igst_exempt",
			"fieldtype": "Check",
			"label": "IGST Also Exempt under Authorisation",
			"default": "1",
			"depends_on": "eval:(doc.items || []).some((row) => row.exim_authorisation) || doc.exim_authorisation",
			"description": "Untick when IGST was paid on this import.",
		},
		{
			"fieldname": "exim_total_duty_foregone",
			"fieldtype": "Currency",
			"label": "Duty Foregone under Authorisation",
			"options": "Company:company:default_currency",
			"read_only": 1,
			"depends_on": "exim_total_duty_foregone",
		},
		{
			"fieldname": "exim_currency",
			"fieldtype": "Link",
			"label": "Invoice Currency",
			"options": "Currency",
			"read_only": 1,
		},
		{
			"fieldname": "exim_customs_exchange_rate",
			"fieldtype": "Float",
			"label": "Customs Exchange Rate",
			"precision": "4",
			"read_only": 1,
		},
		{"fieldname": "exim_duty_column", "fieldtype": "Column Break"},
		{
			"fieldname": "exim_additional_value",
			"fieldtype": "Currency",
			"label": "Freight, Insurance and Other Additions (INR)",
			"options": "Company:company:default_currency",
			"description": "Added to the assessable value and spread over items by value, e.g. freight and insurance on FOB / FCA / EXW imports.",
		},
		{
			"fieldname": "exim_landed_cost_voucher",
			"fieldtype": "Link",
			"label": "Landed Cost Voucher",
			"options": "Landed Cost Voucher",
			"read_only": 1,
			"no_copy": 1,
		},
		{"fieldname": "exim_payment_section", "fieldtype": "Section Break", "label": "Import Payment (FEMA)"},
		{
			"fieldname": "exim_invoice_value",
			"fieldtype": "Currency",
			"label": "Invoice Value",
			"options": "exim_currency",
			"read_only": 1,
		},
		{
			"fieldname": "exim_paid_value",
			"fieldtype": "Currency",
			"label": "Paid",
			"options": "exim_currency",
			"read_only": 1,
			"allow_on_submit": 1,
			"no_copy": 1,
		},
		{"fieldname": "exim_payment_column", "fieldtype": "Column Break"},
		{
			"fieldname": "exim_payment_due_date",
			"fieldtype": "Date",
			"label": "Payment Due By",
			"read_only": 1,
			"no_copy": 1,
		},
		{
			"fieldname": "exim_payment_status",
			"fieldtype": "Select",
			"label": "Payment Status",
			"options": "Unpaid\nPartly Paid\nPaid",
			"default": "Unpaid",
			"read_only": 1,
			"allow_on_submit": 1,
			"no_copy": 1,
			"in_standard_filter": 1,
		},
	],
	"total_amount_payable",
)

CUSTOM_FIELDS["Bill of Entry Item"] = chain(
	[
		{
			"fieldname": "exim_customs_tariff_item",
			"fieldtype": "Link",
			"label": "Tariff Item",
			"options": "Customs Tariff Item",
			"fetch_from": "item_code.exim_customs_tariff_item",
			"fetch_if_empty": 1,
		},
		{
			"fieldname": "exim_authorisation",
			"fieldtype": "Link",
			"label": "Under Authorisation",
			"options": "Export Authorisation",
			"in_list_view": 1,
			"columns": 2,
			"depends_on": "eval:frappe.boot.exim_features?.licences || doc.exim_authorisation",
			"description": "To split one line between a licence and duty payment, duplicate the row and share its quantity.",
		},
		{"fieldname": "exim_value_fc", "fieldtype": "Currency", "label": "Invoice Value (Invoice Currency)"},
		{
			"fieldname": "exim_manual_rates",
			"fieldtype": "Check",
			"label": "Duty Rates Entered Manually",
			"description": "Tick when an exemption notification changes the tariff rate.",
		},
		{"fieldname": "exim_exemption_notification", "fieldtype": "Data", "label": "Exemption Notification"},
		{
			"fieldname": "exim_bcd_rate",
			"fieldtype": "Percent",
			"label": "BCD %",
			"read_only_depends_on": "eval:!doc.exim_manual_rates",
		},
		{
			"fieldname": "exim_sws_rate",
			"fieldtype": "Percent",
			"label": "SWS % of BCD",
			"read_only_depends_on": "eval:!doc.exim_manual_rates",
		},
		{
			"fieldname": "exim_aidc_rate",
			"fieldtype": "Percent",
			"label": "AIDC %",
			"read_only_depends_on": "eval:!doc.exim_manual_rates",
		},
		{
			"fieldname": "exim_other_duty_rate",
			"fieldtype": "Percent",
			"label": "Other Duty % (ADD / Safeguard)",
			"read_only_depends_on": "eval:!doc.exim_manual_rates",
		},
		{"fieldname": "exim_bcd_amount", "fieldtype": "Currency", "label": "BCD", "read_only": 1},
		{"fieldname": "exim_sws_amount", "fieldtype": "Currency", "label": "SWS", "read_only": 1},
		{"fieldname": "exim_aidc_amount", "fieldtype": "Currency", "label": "AIDC", "read_only": 1},
		{
			"fieldname": "exim_other_duty_amount",
			"fieldtype": "Currency",
			"label": "Other Duty",
			"read_only": 1,
		},
		{
			"fieldname": "exim_duty_foregone",
			"fieldtype": "Currency",
			"label": "Customs Duty Foregone",
			"read_only": 1,
			"description": "Basic customs duty not paid because the import is under an Advance Authorisation or EPCG.",
		},
		{
			"fieldname": "exim_igst_foregone",
			"fieldtype": "Currency",
			"label": "IGST Foregone",
			"read_only": 1,
		},
	],
	"cess_non_advol_amount",
)

CUSTOM_FIELDS["Purchase Order"] = [
	flag(
		"exim_is_import",
		"Is Import",
		"is_reverse_charge",
		fetch_from="supplier.exim_is_import",
		description="Overseas purchase. Create > Import Shipment follows it from booking to clearance.",
	)
]
