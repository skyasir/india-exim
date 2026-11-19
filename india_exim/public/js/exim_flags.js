// Tick "Is Export" / "Is Import" when India Compliance marks the party or transaction as Overseas.
// Users can still untick; this only fills an empty tick.
(() => {
	const FLAGS = {
		Customer: "exim_is_export",
		"Sales Order": "exim_is_export",
		"Sales Invoice": "exim_is_export",
		Supplier: "exim_is_import",
		"Purchase Invoice": "exim_is_import",
	};

	for (const [doctype, fieldname] of Object.entries(FLAGS)) {
		frappe.ui.form.on(doctype, {
			gst_category(frm) {
				if (frm.doc.docstatus === 0 && frm.doc.gst_category === "Overseas" && !frm.doc[fieldname]) {
					frm.set_value(fieldname, 1);
				}
			},
		});
	}
})();
