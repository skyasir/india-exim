// Copyright (c) 2026, Yasir Shaikh and contributors
// For license information, please see license.txt

frappe.query_reports["Import Payment Ageing"] = {
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
			fieldname: "as_on_date",
			label: __("As On"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{ fieldname: "supplier", label: __("Supplier"), fieldtype: "Link", options: "Supplier" },
		{ fieldname: "overdue_only", label: __("Overdue Only"), fieldtype: "Check" },
	],
};
