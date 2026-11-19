"""Custom fields India EXIM adds to ERPNext and India Compliance doctypes."""

from india_exim.setup.accounts import EXIM_ACCOUNTS

STATUS_HOLDER_OPTIONS = "\nOne Star Export House\nTwo Star Export House\nThree Star Export House\nFour Star Export House\nFive Star Export House"


def get_company_fields():
	fields = [
		{
			"fieldname": "exim_tab",
			"fieldtype": "Tab Break",
			"label": "EXIM",
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
		},
		{
			"fieldname": "exim_ecgc_policy_number",
			"fieldtype": "Data",
			"label": "ECGC Policy No.",
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
		},
		{
			"fieldname": "exim_rcmc_council",
			"fieldtype": "Data",
			"label": "Export Promotion Council",
			"insert_after": "exim_rcmc_number",
		},
		{
			"fieldname": "exim_rcmc_valid_upto",
			"fieldtype": "Date",
			"label": "RCMC Valid Upto",
			"insert_after": "exim_rcmc_council",
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
				"description": description,
				"insert_after": previous,
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
			"label": "Common",
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


CUSTOM_FIELDS = {
	"Company": get_company_fields(),
	"Item": [
		{
			"fieldname": "exim_customs_tariff_item",
			"fieldtype": "Link",
			"label": "Customs Tariff Item (ITC-HS)",
			"options": "Customs Tariff Item",
			"insert_after": "gst_hsn_code",
			"description": "8-digit ITC-HS code used on shipping bills and bills of entry.",
		},
	],
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


EXPORT_PARTY = "eval:['Overseas', 'SEZ'].includes(doc.gst_category)"
IMPORT_PARTY = "eval:doc.gst_category == 'Overseas'"
PAYMENT_TERMS = "\nAdvance\nLetter of Credit\nDocuments against Payment (DP)\nDocuments against Acceptance (DA)\nOpen Account"
MODES = "\nSea FCL\nSea LCL\nAir\nCourier\nRoad\nRail"


def chain(fields: list[dict], first_insert_after: str) -> list[dict]:
	"""Give each field insert_after = the previous field, so a block keeps its order."""
	previous = first_insert_after
	for field in fields:
		field.setdefault("insert_after", previous)
		previous = field["fieldname"]
	return fields


def get_order_and_invoice_fields(insert_after: str, include_summary: bool) -> list[dict]:
	"""Same fieldnames on Sales Order and Sales Invoice so ERPNext's mapper copies them."""
	fields = [
		{"fieldname": "exim_tab", "fieldtype": "Tab Break", "label": "EXIM", "depends_on": EXPORT_PARTY},
	]
	if include_summary:
		fields += [
			{"fieldname": "exim_summary_section", "fieldtype": "Section Break", "label": "Export Status"},
			{"fieldname": "exim_summary", "fieldtype": "HTML", "label": "Export Status"},
		]
	fields += [
		{"fieldname": "exim_route_section", "fieldtype": "Section Break", "label": "Route"},
		{
			"fieldname": "exim_destination_country",
			"fieldtype": "Link",
			"label": "Destination Country",
			"options": "Country",
		},
		{"fieldname": "exim_port_of_discharge", "fieldtype": "Data", "label": "Port of Discharge"},
		{"fieldname": "exim_final_destination", "fieldtype": "Data", "label": "Final Destination"},
		{"fieldname": "exim_route_column", "fieldtype": "Column Break"},
		{"fieldname": "exim_mode_of_transport", "fieldtype": "Select", "label": "Mode", "options": MODES},
		{"fieldname": "exim_pre_carriage_by", "fieldtype": "Data", "label": "Pre-carriage By"},
		{
			"fieldname": "exim_place_of_receipt",
			"fieldtype": "Data",
			"label": "Place of Receipt by Pre-carrier",
		},
		{"fieldname": "exim_terms_section", "fieldtype": "Section Break", "label": "Payment Terms"},
		{
			"fieldname": "exim_payment_terms_type",
			"fieldtype": "Select",
			"label": "Export Payment Terms",
			"options": PAYMENT_TERMS,
		},
		{
			"fieldname": "exim_lc_number",
			"fieldtype": "Data",
			"label": "LC No.",
			"depends_on": "eval:doc.exim_payment_terms_type == 'Letter of Credit'",
		},
		{"fieldname": "exim_terms_column", "fieldtype": "Column Break"},
		{
			"fieldname": "exim_lc_date",
			"fieldtype": "Date",
			"label": "LC Date",
			"depends_on": "eval:doc.exim_payment_terms_type == 'Letter of Credit'",
		},
		{
			"fieldname": "exim_latest_shipment_date",
			"fieldtype": "Date",
			"label": "Latest Shipment Date",
			"depends_on": "eval:doc.exim_payment_terms_type == 'Letter of Credit'",
		},
		{
			"fieldname": "exim_value_section",
			"fieldtype": "Section Break",
			"label": "FOB Breakup",
			"description": "Freight and insurance included in the invoice value. They are deducted to arrive at the FOB value on the shipping bill.",
		},
		{"fieldname": "exim_freight", "fieldtype": "Currency", "label": "Freight", "options": "currency"},
		{"fieldname": "exim_value_column", "fieldtype": "Column Break"},
		{"fieldname": "exim_insurance", "fieldtype": "Currency", "label": "Insurance", "options": "currency"},
		{"fieldname": "exim_marks_section", "fieldtype": "Section Break", "label": "Marks"},
		{"fieldname": "exim_marks_and_numbers", "fieldtype": "Small Text", "label": "Marks and Numbers"},
	]
	return chain(fields, insert_after)


CUSTOM_FIELDS["Customer"] = chain(
	[
		{"fieldname": "exim_tab", "fieldtype": "Tab Break", "label": "EXIM", "depends_on": EXPORT_PARTY},
		{
			"fieldname": "exim_documents_section",
			"fieldtype": "Section Break",
			"label": "Buyer Document Instructions",
		},
		{"fieldname": "exim_notify_party", "fieldtype": "Small Text", "label": "Notify Party"},
		{
			"fieldname": "exim_consignee",
			"fieldtype": "Small Text",
			"label": "Consignee on Transport Document",
			"description": "e.g. 'To Order of XYZ Bank' when it differs from the buyer.",
		},
		{"fieldname": "exim_documents_column", "fieldtype": "Column Break"},
		{"fieldname": "exim_originals_required", "fieldtype": "Int", "label": "Sets of Originals Required"},
		{"fieldname": "exim_preferred_courier", "fieldtype": "Data", "label": "Courier for Originals"},
		{"fieldname": "exim_instructions_section", "fieldtype": "Section Break"},
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
	],
	"supplier_numbers",
)

CUSTOM_FIELDS["Supplier"] = chain(
	[
		{"fieldname": "exim_tab", "fieldtype": "Tab Break", "label": "EXIM", "depends_on": IMPORT_PARTY},
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
		{"fieldname": "exim_origin_column", "fieldtype": "Column Break"},
		{
			"fieldname": "exim_origin_documents",
			"fieldtype": "Small Text",
			"label": "Documents Usually Supplied",
		},
	],
	"customer_numbers",
)

CUSTOM_FIELDS["Sales Order"] = get_order_and_invoice_fields("proforma_html", include_summary=False)
CUSTOM_FIELDS["Sales Invoice"] = CUSTOM_FIELDS["Sales Invoice"] + get_order_and_invoice_fields(
	"is_discounted", include_summary=True
)

CUSTOM_FIELDS["Purchase Invoice"] = chain(
	[
		{"fieldname": "exim_tab", "fieldtype": "Tab Break", "label": "EXIM", "depends_on": IMPORT_PARTY},
		{"fieldname": "exim_origin_section", "fieldtype": "Section Break", "label": "Origin"},
		{
			"fieldname": "exim_origin_country",
			"fieldtype": "Link",
			"label": "Country of Origin",
			"options": "Country",
		},
		{"fieldname": "exim_fta_claimed", "fieldtype": "Check", "label": "FTA Concession to be Claimed"},
		{
			"fieldname": "exim_certificate_of_origin",
			"fieldtype": "Data",
			"label": "Certificate of Origin No.",
			"depends_on": "exim_fta_claimed",
		},
		{"fieldname": "exim_origin_column", "fieldtype": "Column Break"},
		{"fieldname": "exim_port_of_loading", "fieldtype": "Data", "label": "Port of Loading (Foreign)"},
		{
			"fieldname": "exim_port_of_discharge",
			"fieldtype": "Data",
			"label": "Port of Discharge (Indian Port Code)",
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
	],
	"cess_non_advol_amount",
)
