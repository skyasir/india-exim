// Copyright (c) 2026, Yasir Shaikh and contributors
// For license information, please see license.txt

frappe.query_reports["Export Realisation Ageing"] = {
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
		{ fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer" },
		{
			fieldname: "destination_country",
			label: __("Destination"),
			fieldtype: "Link",
			options: "Country",
		},
		{ fieldname: "overdue_only", label: __("Overdue Only"), fieldtype: "Check" },
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "overdue_days" && data && data.overdue_days > 0) {
			value = `<span style="color: var(--red-600)">${value}</span>`;
		}
		return value;
	},
};
