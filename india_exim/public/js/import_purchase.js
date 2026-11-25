// Purchase Order and Purchase Invoice: start the Import Shipment that follows the goods.
(() => {
	// loaded for two doctypes, so evaluated once per form type; register once
	if (window.__exim_import_purchase_loaded) return;
	window.__exim_import_purchase_loaded = true;

	const MODULE = "india_exim.imports.doctype.import_shipment.import_shipment";
	const add = (frm, method) => {
		if (frm.doc.docstatus !== 1 || !frm.doc.exim_is_import || frm.doc.is_return) return;
		if (frm.doc.exim_import_shipment || !frappe.model.can_create("Import Shipment")) return;
		frm.add_custom_button(
			__("Import Shipment"),
			() => frappe.model.open_mapped_doc({ method: `${MODULE}.${method}`, frm }),
			__("Create")
		);
	};
	frappe.ui.form.on("Purchase Order", {
		refresh: (frm) => add(frm, "make_from_purchase_order"),
	});
	frappe.ui.form.on("Purchase Invoice", {
		refresh: (frm) => add(frm, "make_from_purchase_invoice"),
	});
})();
