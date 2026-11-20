// Copyright (c) 2026, Yasir Shaikh and contributors
// For license information, please see license.txt

frappe.ui.form.on("Export Shipment", {
	setup(frm) {
		frm.set_query("sales_invoice", "invoices", () => ({
			filters: {
				company: frm.doc.company,
				customer: frm.doc.customer,
				docstatus: 1,
				is_return: 0,
			},
		}));
		for (const field of ["freight_forwarder", "cha"]) {
			frm.set_query(field, () => ({ filters: { disabled: 0 } }));
		}
	},

	refresh(frm) {
		if (frm.is_new()) return;
		frm.dashboard.add_indicator(
			__("Documents Ready: {0}%", [frm.doc.readiness_percent || 0]),
			frm.doc.readiness_percent >= 100
				? "green"
				: frm.doc.readiness_percent >= 50
				? "orange"
				: "red"
		);
		frm.add_custom_button(__("Refresh Document Checklist"), () =>
			frappe
				.call({
					method: "india_exim.exports.doctype.export_shipment.export_shipment.refresh_document_checklist",
					args: { name: frm.doc.name },
					freeze: true,
				})
				.then(({ message }) => {
					frappe.show_alert({
						message: __("{0} document(s) added, {1} in total", [
							message.added,
							message.total,
						]),
						indicator: "green",
					});
					frm.reload_doc();
				})
		);
		frm.add_custom_button(
			__("Shipping Bill"),
			() =>
				frappe.model.open_mapped_doc({
					method: "india_exim.exports.doctype.export_shipment.export_shipment.make_shipping_bill",
					frm,
				}),
			__("Create")
		);
	},
});
