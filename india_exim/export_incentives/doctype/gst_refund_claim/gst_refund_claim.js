// Copyright (c) 2026, Yasir Shaikh and contributors
// For license information, please see license.txt

const IGST_REFUND = "IGST Paid on Exports";
const REFUND_MODULE = "india_exim.export_incentives.doctype.gst_refund_claim.gst_refund_claim";

frappe.ui.form.on("GST Refund Claim", {
	setup(frm) {
		frm.set_query("credit_account", () => ({
			filters: { company: frm.doc.company, is_group: 0 },
		}));
		frm.set_query("shipping_bills", () => ({
			filters: {
				company: frm.doc.company,
				docstatus: 1,
				export_type: "With Payment of IGST",
			},
		}));
	},

	company: set_credit_account,
	refund_type: set_credit_account,

	onload(frm) {
		if (frm.is_new()) set_credit_account(frm);
	},

	refresh(frm) {
		if (cint(frm.doc.docstatus) === 0 && frm.doc.refund_type === IGST_REFUND) {
			frm.add_custom_button(__("Get Shipping Bills"), () => get_shipping_bills(frm));
		}
		const pending = (frm.doc.sanctioned_amount || 0) - (frm.doc.received_amount || 0);
		if (frm.doc.docstatus !== 1 || !frm.doc.sanction_date || pending <= 0) return;
		frm.add_custom_button(
			__("Record Refund Receipt"),
			() => {
				const dialog = new frappe.ui.Dialog({
					title: __("Record Refund Receipt"),
					fields: [
						{
							fieldname: "posting_date",
							fieldtype: "Date",
							label: __("Date"),
							reqd: 1,
							default: "Today",
						},
						{
							fieldname: "amount",
							fieldtype: "Currency",
							label: __("Amount"),
							reqd: 1,
							default: pending,
						},
						{
							fieldname: "bank_account",
							fieldtype: "Link",
							options: "Account",
							label: __("Bank Account"),
							reqd: 1,
							get_query: () => ({
								filters: {
									company: frm.doc.company,
									account_type: "Bank",
									is_group: 0,
								},
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
			},
			__("Create")
		);
	},
});

function set_credit_account(frm) {
	frm.remove_custom_button(__("Get Shipping Bills"));
	if (cint(frm.doc.docstatus) === 0 && frm.doc.refund_type === IGST_REFUND) {
		frm.add_custom_button(__("Get Shipping Bills"), () => get_shipping_bills(frm));
	}
	if (!frm.doc.company || frm.doc.refund_type !== IGST_REFUND || frm.doc.credit_account) return;
	frappe.db
		.get_value("Company", frm.doc.company, "exim_igst_refund_receivable_account")
		.then(({ message }) =>
			frm.set_value("credit_account", message?.exim_igst_refund_receivable_account)
		);
}

function get_shipping_bills(frm) {
	if (!frm.doc.company || !frm.doc.from_date || !frm.doc.to_date) {
		frappe.msgprint(__("Enter the company and the tax period first."));
		return;
	}
	frappe
		.xcall(`${REFUND_MODULE}.get_shipping_bills`, {
			company: frm.doc.company,
			from_date: frm.doc.from_date,
			to_date: frm.doc.to_date,
			claim: frm.is_new() ? null : frm.doc.name,
		})
		.then(({ shipping_bills, igst }) => {
			if (!shipping_bills.length) {
				frappe.msgprint(__("No shipping bills with IGST paid and LEO in this period."));
				return;
			}
			frm.set_value(
				"shipping_bills",
				shipping_bills.map((shipping_bill) => ({ shipping_bill }))
			);
			frm.set_value("claimed_amount", igst);
		});
}
