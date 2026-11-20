// Copyright (c) 2026, Yasir Shaikh and contributors
// For license information, please see license.txt

frappe.ui.form.on("Export Authorisation", {
	setup(frm) {
		for (const table of ["imports", "exports"]) {
			frm.set_query("item_code", table, (doc, cdt, cdn) => {
				const row = locals[cdt][cdn];
				return row.customs_tariff_item
					? { filters: { exim_customs_tariff_item: row.customs_tariff_item } }
					: {};
			});
		}
	},

	refresh(frm) {
		if (frm.is_new()) return;
		const colour = {
			Active: "blue",
			"EO Fulfilled": "green",
			Redeemed: "green",
			"EO Period Over": "red",
		};
		frm.dashboard.add_indicator(
			__("Export obligation {0}% fulfilled", [Math.round(frm.doc.eo_percent || 0)]),
			frm.doc.eo_percent >= 100 ? "green" : "orange"
		);
		frm.page.set_indicator(__(frm.doc.status), colour[frm.doc.status] || "gray");
	},

	scheme(frm) {
		const epcg = frm.doc.scheme === "EPCG";
		frm.set_value({ drawback_admissible: epcg ? 1 : 0, rodtep_admissible: epcg ? 1 : 0 });
	},
});
