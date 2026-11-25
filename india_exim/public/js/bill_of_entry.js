/* global india_exim */
// Evidence pack for a Bill of Entry: one ZIP with the bill, import invoices, landed cost,
// payments, attachments and change history. See india_exim/utils/evidence_pack.py.
frappe.ui.form.on("Bill of Entry", {
	refresh(frm) {
		if (cint(frm.doc.docstatus) === 0 && frappe.model.can_write("Customs Tariff Item")) {
			frm.add_custom_button(__("Add Duty Rate"), () => add_duty_rate(frm));
		}
		if (frm.doc.docstatus !== 1) return;
		if (frm.doc.exim_landed_cost_voucher) {
			// made on submit; a second one would add the duty to stock twice
			setTimeout(() => frm.remove_custom_button(__("Landed Cost Voucher"), __("Create")));
		}
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

// a rate entered once here is kept on the tariff code for the next bill
async function add_duty_rate(frm) {
	const codes = [...new Set(frm.doc.items.map((row) => row.item_code).filter(Boolean))];
	const tariffs = new Set(frm.doc.items.map((row) => row.exim_customs_tariff_item));
	for (const item of codes) {
		const { message } = await frappe.db.get_value("Item", item, "exim_customs_tariff_item");
		tariffs.add(message?.exim_customs_tariff_item);
	}
	const options = [...tariffs].filter(Boolean);
	if (!options.length) {
		frappe.msgprint(__("Set the ITC-HS code on the items first."));
		return;
	}
	const add = (tariff) =>
		india_exim.rates.add_duty(
			tariff,
			() =>
				frappe.show_alert({
					message: __("Duty rate added. Save to calculate the duty."),
					indicator: "green",
				}),
			frm.doc.bill_of_entry_date
		);
	if (options.length === 1) return add(options[0]);
	frappe.prompt(
		{
			fieldname: "tariff",
			fieldtype: "Select",
			label: __("ITC-HS Code"),
			options,
			reqd: 1,
		},
		({ tariff }) => add(tariff),
		__("Add Duty Rate")
	);
}
