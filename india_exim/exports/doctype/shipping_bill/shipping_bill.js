// Copyright (c) 2026, Yasir Shaikh and contributors
// For license information, please see license.txt

frappe.ui.form.on("Shipping Bill", {
	setup(frm) {
		frm.set_query("export_shipment", () => ({
			filters: { company: frm.doc.company, customer: frm.doc.customer, status: ["!=", "Cancelled"] },
		}));
		frm.set_query("sales_invoice", "items", () => ({
			filters: { company: frm.doc.company, customer: frm.doc.customer, docstatus: 1 },
		}));
	},

	refresh(frm) {
		set_status_indicator(frm);
		if (frm.doc.docstatus === 1 && frm.doc.accrual_journal_entry) {
			frm.add_custom_button(__("Incentive Accrual"), () =>
				frappe.set_route("Form", "Journal Entry", frm.doc.accrual_journal_entry)
			, __("View"));
		}
	},

	get_items_from_invoices(frm) {
		if (!frm.doc.customer) {
			frappe.msgprint(__("Select the customer first."));
			return;
		}
		new frappe.ui.form.MultiSelectDialog({
			doctype: "Sales Invoice",
			target: frm,
			setters: { posting_date: null },
			add_filters_group: 1,
			get_query: () => ({
				filters: { company: frm.doc.company, customer: frm.doc.customer, docstatus: 1, is_return: 0 },
			}),
			action(selections) {
				if (!selections.length) return;
				frappe
					.call({
						method: "india_exim.exports.doctype.shipping_bill.shipping_bill.get_items_from_sales_invoices",
						args: { sales_invoices: selections },
					})
					.then(({ message }) => {
						const existing = new Set((frm.doc.items || []).map((row) => row.sales_invoice_item));
						(message || [])
							.filter((row) => !existing.has(row.sales_invoice_item))
							.forEach((row) => frm.add_child("items", row));
						frm.refresh_field("items");
						this.dialog.hide();
					});
			},
		});
	},
});

function set_status_indicator(frm) {
	const colours = {
		Draft: "red",
		Filed: "blue",
		"LEO Granted": "orange",
		"EGM Filed": "green",
		Cancelled: "red",
	};
	if (frm.doc.status) frm.page.set_indicator(__(frm.doc.status), colours[frm.doc.status] || "gray");
}
