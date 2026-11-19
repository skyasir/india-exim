// Copyright (c) 2026, Yasir Shaikh and contributors
// For license information, please see license.txt

frappe.ui.form.on("RoDTEP Scrip", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1 || frm.doc.balance_amount <= 0) return;
		frm.add_custom_button(__("Pay Customs Duty"), () => utilise_dialog(frm, "Customs Duty"), __("Use Scrip"));
		frm.add_custom_button(__("Sell Scrip"), () => utilise_dialog(frm, "Sale"), __("Use Scrip"));
	},
});

function utilise_dialog(frm, utilisation_type) {
	const is_sale = utilisation_type === "Sale";
	const dialog = new frappe.ui.Dialog({
		title: is_sale ? __("Sell Scrip") : __("Pay Customs Duty with Scrip"),
		fields: [
			{ fieldname: "posting_date", fieldtype: "Date", label: __("Date"), reqd: 1, default: "Today" },
			{
				fieldname: "amount",
				fieldtype: "Currency",
				label: __("Scrip Value Used"),
				reqd: 1,
				default: frm.doc.balance_amount,
			},
			{
				fieldname: "bill_of_entry",
				fieldtype: "Link",
				options: "Bill of Entry",
				label: __("Bill of Entry"),
				reqd: !is_sale,
				hidden: is_sale,
				get_query: () => ({ filters: { company: frm.doc.company, docstatus: 1 } }),
			},
			{ fieldname: "sale_value", fieldtype: "Currency", label: __("Sale Consideration"), reqd: is_sale, hidden: !is_sale },
			{
				fieldname: "bank_account",
				fieldtype: "Link",
				options: "Account",
				label: __("Received In"),
				reqd: is_sale,
				hidden: !is_sale,
				get_query: () => ({
					filters: { company: frm.doc.company, account_type: ["in", ["Bank", "Cash"]], is_group: 0 },
				}),
			},
		],
		primary_action_label: __("Record"),
		primary_action(values) {
			frappe
				.call({
					method: "india_exim.export_incentives.doctype.rodtep_scrip.rodtep_scrip.utilise_scrip",
					args: { scrip: frm.doc.name, utilisation_type, ...values },
					freeze: true,
				})
				.then(() => {
					dialog.hide();
					frm.reload_doc();
				});
		},
	});
	dialog.show();
}
