// Copyright (c) 2026, Yasir Shaikh and contributors
// For license information, please see license.txt

frappe.query_reports["Pending Trade Documents"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{ fieldname: "responsible", label: __("Responsible"), fieldtype: "Link", options: "User" },
		{ fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer" },
		{ fieldname: "mandatory_only", label: __("Mandatory Only"), fieldtype: "Check", default: 1 },
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
