frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		const is_export = ["Overseas", "SEZ"].includes(frm.doc.gst_category);
		if (frm.doc.docstatus !== 1 || !is_export || frm.doc.is_return) return;

		frm.add_custom_button(
			__("Shipping Bill"),
			() =>
				frappe.model.open_mapped_doc({
					method: "india_exim.exports.doctype.shipping_bill.shipping_bill.make_shipping_bill",
					frm,
				}),
			__("Create")
		);
		frm.add_custom_button(
			__("Export Shipment"),
			() =>
				frappe.model.open_mapped_doc({
					method: "india_exim.overrides.sales_invoice.make_export_shipment",
					frm,
				}),
			__("Create")
		);
	},
});
