// Copyright (c) 2026, Yasir Shaikh and contributors
// For license information, please see license.txt

const CLAIM_MODULE =
	"india_exim.export_incentives.doctype.export_incentive_claim.export_incentive_claim";

frappe.ui.form.on("Export Incentive Claim", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1 || frm.doc.outstanding_amount <= 0) return;
		if (frm.doc.scheme === "RoDTEP") {
			frm.add_custom_button(
				__("Create RoDTEP Scrip"),
				() => create_scrip_dialog(frm),
				__("Create")
			);
		} else {
			frm.add_custom_button(__("Record Receipt"), () => receipt_dialog(frm), __("Create"));
		}
	},

	get_shipping_bills(frm) {
		if (!frm.doc.company || !frm.doc.scheme) {
			frappe.msgprint(__("Select the company and scheme first."));
			return;
		}
		frappe
			.call({
				method: `${CLAIM_MODULE}.get_unclaimed_shipping_bills`,
				args: {
					company: frm.doc.company,
					scheme: frm.doc.scheme,
					from_date: frm.doc.from_date,
					to_date: frm.doc.to_date,
				},
			})
			.then(({ message }) => {
				const existing = new Set((frm.doc.items || []).map((row) => row.shipping_bill));
				const rows = (message || []).filter((row) => !existing.has(row.shipping_bill));
				rows.forEach((row) =>
					frm.add_child("items", { ...row, sanctioned_amount: row.expected_amount })
				);
				frm.refresh_field("items");
				frappe.show_alert({
					message: __("{0} shipping bill(s) added", [rows.length]),
					indicator: "green",
				});
			});
	},
});

function receipt_dialog(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("Record {0} Receipt", [frm.doc.scheme]),
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
				default: frm.doc.outstanding_amount,
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
						account_type: ["in", ["Bank", "Cash"]],
						is_group: 0,
					},
				}),
			},
		],
		primary_action_label: __("Record"),
		primary_action(values) {
			frappe
				.call({
					method: `${CLAIM_MODULE}.record_receipt`,
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
}

function create_scrip_dialog(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("Record RoDTEP e-Scrip"),
		fields: [
			{ fieldname: "scrip_number", fieldtype: "Data", label: __("e-Scrip No."), reqd: 1 },
			{
				fieldname: "scrip_date",
				fieldtype: "Date",
				label: __("Scrip Date"),
				reqd: 1,
				default: "Today",
			},
			{
				fieldname: "face_value",
				fieldtype: "Currency",
				label: __("Face Value"),
				reqd: 1,
				default: frm.doc.outstanding_amount,
			},
		],
		primary_action_label: __("Create"),
		primary_action(values) {
			frappe
				.call({
					method: `${CLAIM_MODULE}.create_rodtep_scrip`,
					args: { claim: frm.doc.name, ...values },
					freeze: true,
				})
				.then(({ message }) => {
					dialog.hide();
					frappe.set_route("Form", "RoDTEP Scrip", message);
				});
		},
	});
	dialog.show();
}
