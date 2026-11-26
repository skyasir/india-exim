// Copyright (c) 2026, Yasir Shaikh and contributors
// For license information, please see license.txt

frappe.ui.form.on("Certificate of Origin", {
	setup(frm) {
		frm.set_query("shipping_bill", (doc) => ({
			filters: { docstatus: ["!=", 2], ...(doc.company ? { company: doc.company } : {}) },
		}));
		frm.set_query("sales_invoice", (doc) => ({
			filters: { docstatus: 1, ...(doc.company ? { company: doc.company } : {}) },
		}));
	},

	refresh(frm) {
		const colour = { Draft: "gray", Applied: "blue", Issued: "green", Rejected: "red" };
		if (!frm.is_new()) frm.page.set_indicator(__(frm.doc.status), colour[frm.doc.status]);
	},

	shipping_bill(frm) {
		// the goods are taken from the new shipping bill when the form is saved
		if (frm.doc.shipping_bill) frm.clear_table("items");
		frm.refresh_field("items");
	},

	sales_invoice(frm) {
		if (frm.doc.sales_invoice && !frm.doc.shipping_bill) frm.clear_table("items");
		frm.refresh_field("items");
	},

	certificate_type(frm) {
		if (frm.doc.certificate_type !== "Preferential") frm.set_value("trade_agreement", "");
		if (frm.doc.certificate_type === "Non-Preferential" && !frm.doc.issuing_agency)
			frm.set_value("issuing_agency", "Chamber of Commerce");
	},
});
