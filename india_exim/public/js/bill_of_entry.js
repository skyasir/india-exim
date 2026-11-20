// Evidence pack for a Bill of Entry: one ZIP with the bill, import invoices, landed cost,
// payments, attachments and change history. See india_exim/utils/evidence_pack.py.
frappe.ui.form.on("Bill of Entry", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1) return;
		frm.add_custom_button(
			__("Evidence Pack"),
			() =>
				window.open(
					frappe.urllib.get_full_url(
						"/api/method/india_exim.utils.evidence_pack.download_evidence_pack?" +
							new URLSearchParams({ doctype: frm.doctype, name: frm.doc.name })
					)
				),
			__("View")
		);
	},
});
