// Copyright (c) 2026, Yasir Shaikh and contributors
// For license information, please see license.txt

frappe.ui.form.on("GST Refund Claim", {
	setup(frm) {
		frm.set_query("credit_account", () => ({ filters: { company: frm.doc.company, is_group: 0 } }));
		frm.set_query("shipping_bill", "shipping_bills", () => ({
			filters: { company: frm.doc.company, docstatus: 1, export_type: "With Payment of IGST" },
		}));
	},

	refresh(frm) {
		const pending = (frm.doc.sanctioned_amount || 0) - (frm.doc.received_amount || 0);
		if (frm.doc.docstatus !== 1 || !frm.doc.sanction_date || pending <= 0) return;
		frm.add_custom_button(__("Record Refund Receipt"), () => {
			const dialog = new frappe.ui.Dialog({
				title: __("Record Refund Receipt"),
				fields: [
					{ fieldname: "posting_date", fieldtype: "Date", label: __("Date"), reqd: 1, default: "Today" },
					{ fieldname: "amount", fieldtype: "Currency", label: __("Amount"), reqd: 1, default: pending },
					{
						fieldname: "bank_account",
						fieldtype: "Link",
						options: "Account",
						label: __("Bank Account"),
						reqd: 1,
						get_query: () => ({
							filters: { company: frm.doc.company, account_type: "Bank", is_group: 0 },
						}),
					},
				],
				primary_action_label: __("Record"),
				primary_action(values) {
					frappe
						.call({
							method: "india_exim.export_incentives.doctype.gst_refund_claim.gst_refund_claim.record_refund_receipt",
							args: { claim: frm.doc.name, ...values },
							freeze: true,
						})
						.then(() => {
							dialog.hide();
							frm.reload_doc();
						});
				},
			});
			dialog.show();
		}, __("Create"));
	},
});
