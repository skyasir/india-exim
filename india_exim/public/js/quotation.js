// Export quotation: open an Export Costing Sheet for it (EXW -> FOB -> CIF price build-up).
frappe.ui.form.on("Quotation", {
	refresh(frm) {
		if (frm.doc.docstatus !== 0 || frm.is_new() || !frm.doc.exim_is_export) return;
		frm.add_custom_button(
			__("Export Costing Sheet"),
			() =>
				frappe.model.open_mapped_doc({
					method: "india_exim.exports.doctype.export_costing_sheet.export_costing_sheet.make_costing_sheet",
					frm,
				}),
			__("Create")
		);
	},
});
