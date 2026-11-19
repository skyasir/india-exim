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
		{
			"fieldname": "exim_accounts_section",
			"fieldtype": "Section Break",
			"label": "Default EXIM Accounts",
			"insert_after": "exim_rcmc_valid_upto",
			"description": "Created automatically when India EXIM is installed. Review and change if your chart of accounts uses different heads.",
		},
	]

	previous = "exim_accounts_section"
	for index, (fieldname, spec) in enumerate(EXIM_ACCOUNTS.items()):
		if index and index % 6 == 0:
			column = f"exim_accounts_column_{index}"
			fields.append({"fieldname": column, "fieldtype": "Column Break", "insert_after": previous})
			previous = column
		fields.append(
			{
				"fieldname": fieldname,
				"fieldtype": "Link",
				"label": spec["label"],
				"options": "Account",
				"insert_after": previous,
			}
		)
		previous = fieldname

	fields += [
		{
			"fieldname": "exim_cost_center",
			"fieldtype": "Link",
			"label": "EXIM Cost Center",
			"options": "Cost Center",
			"insert_after": previous,
		},
		{
			"fieldname": "exim_forex_gain_loss_account",
			"fieldtype": "Link",
			"label": "Forex Gain / Loss on Realisation",
			"options": "Account",
			"insert_after": "exim_cost_center",
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
