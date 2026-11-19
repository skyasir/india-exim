// Copyright (c) 2026, Yasir Shaikh and contributors
// For license information, please see license.txt

frappe.query_reports["Shipping Bill Register"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: erpnext.utils.get_fiscal_year(frappe.datetime.get_today(), true)[1],
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{ fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer" },
		{
			fieldname: "destination_country",
			label: __("Destination"),
			fieldtype: "Link",
			options: "Country",
		},
		{
			fieldname: "export_type",
			label: __("Export Type"),
			fieldtype: "Select",
			options: [
				"",
				"Under LUT / Bond (without IGST)",
				"With Payment of IGST",
				"Free of Cost / Sample",
			],
		},
		{ fieldname: "port_code", label: __("Port Code"), fieldtype: "Data" },
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: ["", "Filed", "LEO Granted", "EGM Filed"],
		},
	],
};
