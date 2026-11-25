// Tick "Is Export" / "Is Import" when India Compliance marks the party or transaction as Overseas.
// Users can still untick; this only fills an empty tick.
(() => {
	const FLAGS = {
		Customer: "exim_is_export",
		Quotation: "exim_is_export",
		"Sales Order": "exim_is_export",
		"Delivery Note": "exim_is_export",
		"Sales Invoice": "exim_is_export",
		Supplier: "exim_is_import",
		"Purchase Order": "exim_is_import",
		"Purchase Invoice": "exim_is_import",
	};

	// a quotation's party may be a Lead, so the customer's tick is fetched here, not by fetch_from
	frappe.ui.form.on("Quotation", {
		party_name(frm) {
			if (
				frm.doc.docstatus !== 0 ||
				frm.doc.quotation_to !== "Customer" ||
				!frm.doc.party_name
			)
				return;
			frappe.db
				.get_value("Customer", frm.doc.party_name, "exim_is_export")
				.then(({ message }) => {
					if (message?.exim_is_export && !frm.doc.exim_is_export)
						frm.set_value("exim_is_export", 1);
				});
		},
	});

	for (const [doctype, fieldname] of Object.entries(FLAGS)) {
		frappe.ui.form.on(doctype, {
			gst_category(frm) {
				if (
					frm.doc.docstatus === 0 &&
					frm.doc.gst_category === "Overseas" &&
					!frm.doc[fieldname]
				) {
					frm.set_value(fieldname, 1);
				}
			},
		});
	}
})();
