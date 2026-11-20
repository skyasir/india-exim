// Copyright (c) 2026, Yasir Shaikh and contributors
// For license information, please see license.txt

frappe.ui.form.on("Export Costing Sheet", {
	setup(frm) {
		frm.set_query("quotation", () => ({ filters: { company: frm.doc.company, docstatus: 0 } }));
	},

	refresh(frm) {
		if (frm.is_new() || !frm.doc.quotation) return;
		frm.add_custom_button(__("Update Quotation Rates"), () =>
			frappe
				.call({
					method: "india_exim.exports.doctype.export_costing_sheet.export_costing_sheet.update_quotation_rates",
					args: { name: frm.doc.name },
					freeze: true,
				})
				.then(({ message }) => {
					frappe.show_alert({
						message: __("{0} quotation line(s) updated", [message]),
						indicator: "green",
					});
				})
		);
	},

	currency(frm) {
		if (!frm.doc.currency || !frm.doc.company) return;
		const company_currency = frappe.get_doc(":Company", frm.doc.company)?.default_currency || "INR";
		frappe
			.call({
				method: "erpnext.setup.utils.get_exchange_rate",
				args: { from_currency: frm.doc.currency, to_currency: company_currency, transaction_date: frm.doc.posting_date },
			})
			.then(({ message }) => message && frm.set_value("exchange_rate", message));
	},
});
