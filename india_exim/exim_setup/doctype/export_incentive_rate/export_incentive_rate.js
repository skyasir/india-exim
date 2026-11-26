// Copyright (c) 2026, Yasir Shaikh and contributors
// For license information, please see license.txt

frappe.ui.form.on("Export Incentive Rate", {
	refresh(frm) {
		if (frm.is_new() || frm.doc.data_source) return;
		frappe
			.xcall("india_exim.setup.tariff_data.get_notified_for_rate", { name: frm.doc.name })
			.then((notified) => {
				if (!notified) return;
				frm.dashboard.set_headline_alert(
					__("This rate was entered by hand. The notified rate is {0}.", [
						notified.text,
					]),
					"orange"
				);
				frm.add_custom_button(__("Use Notified Rate"), () => {
					frappe.confirm(
						__(
							"Replace the rates entered by hand for {0} with the notified rates? This deletes them.",
							[frm.doc.customs_tariff_item]
						),
						() =>
							frappe
								.xcall("india_exim.setup.tariff_data.use_notified_rates", {
									name: frm.doc.name,
								})
								.then(() => frappe.set_route("List", "Export Incentive Rate"))
					);
				});
			});
	},
});
