// Copyright (c) 2026, Yasir Shaikh and contributors
// For license information, please see license.txt

frappe.query_reports["Export Incentive Register"] = {
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
			label: __("LEO From"),
			fieldtype: "Date",
			default: erpnext.utils.get_fiscal_year(frappe.datetime.get_today(), true)[1],
		},
		{
			fieldname: "to_date",
			label: __("LEO To"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "scheme",
			label: __("Scheme"),
			fieldtype: "Select",
			options: ["", "Duty Drawback", "RoDTEP"],
		},
		{ fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer" },
		{ fieldname: "pending_only", label: __("Receivable Only"), fieldtype: "Check" },
	],
};
