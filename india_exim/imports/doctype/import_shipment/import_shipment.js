// Copyright (c) 2026, Yasir Shaikh and contributors
// For license information, please see license.txt

const IMPORT_SHIPMENT = "india_exim.imports.doctype.import_shipment.import_shipment";

frappe.ui.form.on("Import Shipment", {
	setup(frm) {
		const filters = () => ({
			company: frm.doc.company,
			supplier: frm.doc.supplier,
			docstatus: 1,
		});
		frm.set_query("purchase_order", "orders", () => ({ filters: filters() }));
		frm.set_query("purchase_invoice", "invoices", () => ({
			filters: { ...filters(), is_return: 0 },
		}));
	},

	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Refresh Document Checklist"), () =>
			frappe
				.call({
					method: `${IMPORT_SHIPMENT}.refresh_document_checklist`,
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
	},
});
