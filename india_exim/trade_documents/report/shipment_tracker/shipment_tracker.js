// Copyright (c) 2026, Yasir Shaikh and contributors
// For license information, please see license.txt

frappe.query_reports["Shipment Tracker"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{ fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer" },
		{
			fieldname: "destination_country",
			label: __("Destination"),
			fieldtype: "Link",
			options: "Country",
		},
		{
			fieldname: "status",
			label: __("Stage"),
			fieldtype: "Select",
			options: [
				"",
				"Planned",
				"Booked",
				"Stuffed",
				"Customs Cleared",
				"Shipped",
				"Documents Sent",
			],
		},
		{
			fieldname: "cutoff_within_hours",
			label: __("Cut-off Within (Hours)"),
			fieldtype: "Int",
		},
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (
			column.fieldname === "hours_left" &&
			data &&
			data.hours_left != null &&
			data.hours_left <= 48
		) {
			value = `<span style="color: var(--red-600); font-weight: 600">${value}</span>`;
		}
		return value;
	},
};
