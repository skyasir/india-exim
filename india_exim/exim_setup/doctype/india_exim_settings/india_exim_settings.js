// Copyright (c) 2026, Yasir Shaikh and contributors
// For license information, please see license.txt

frappe.ui.form.on("India EXIM Settings", {
	after_save() {
		// the switches reach the forms and the menu through boot
		setTimeout(() => window.location.reload(), 800);
	},

	refresh(frm) {
		if (frappe.user.has_role(["System Manager", "EXIM Manager"])) {
			frm.add_custom_button(__("Quick Setup"), () => quick_setup());
			frm.change_custom_button_type(__("Quick Setup"), null, "primary");
			if (frappe.route_options?.quick_setup) {
				frappe.route_options = null;
				quick_setup();
			}
		}
		if (!frappe.user.has_role("System Manager")) return;
		frm.add_custom_button(__("Reload Tariff Data"), () => {
			frappe.confirm(
				__(
					"Load India EXIM's tariff items and RoDTEP rates again? Rates you entered yourself are kept."
				),
				() =>
					frappe
						.xcall("india_exim.setup.tariff_data.reload_tariff_data")
						.then((summary) => {
							const lines = Object.entries(summary).map(
								([pack, s]) =>
									`${pack}: ${s.tariff_items_created} ${__("tariff items")}, ${
										s.rates_created
									} ${__("rates added")}, ${s.rates_updated} ${__("updated")}, ${
										s.kept_own_rates
									} ${__("kept as entered")}`
							);
							frappe.msgprint(lines.join("<br>"), __("Tariff Data"));
						})
			);
		});
	},
});

function quick_setup() {
	const METHOD = "india_exim.exim_setup.quick_setup";
	const exports = "eval:doc.business_type != 'Import'";
	const check = (fieldname, label, depends_on) => ({
		fieldname,
		fieldtype: "Check",
		label,
		depends_on,
	});
	const dialog = new frappe.ui.Dialog({
		title: __("Quick Setup"),
		size: "large",
		fields: [
			{
				fieldname: "company",
				fieldtype: "Link",
				options: "Company",
				label: __("Company"),
				reqd: 1,
				default: frappe.defaults.get_user_default("Company"),
				onchange: () => load(),
			},
			{ fieldtype: "Column Break" },
			{
				fieldname: "exim_iec",
				fieldtype: "Data",
				label: __("Importer-Exporter Code (IEC)"),
				description: __("10 characters, same as the company PAN."),
			},
			{
				fieldname: "business_type",
				fieldtype: "Select",
				options: "Export\nImport\nBoth",
				label: __("Business Type"),
				default: "Export",
				reqd: 1,
				description: __("Only what you do is shown."),
			},
			{ fieldtype: "Section Break", label: __("Bank and Port") },
			{ fieldname: "ad_code", fieldtype: "Data", label: __("AD Code"), depends_on: exports },
			{ fieldname: "bank", fieldtype: "Link", options: "Bank", label: __("Bank") },
			{ fieldtype: "Column Break" },
			{
				fieldname: "port_code",
				fieldtype: "Link",
				options: "Port Master",
				label: __("Main Port"),
				description: __("Where your shipping bills are filed, e.g. Nhava Sheva (INNSA1)."),
				get_query: () => ({ filters: { port_country: "India", disabled: 0 } }),
			},
			{
				fieldtype: "Section Break",
				label: __("Letter of Undertaking (exports without IGST)"),
				depends_on: exports,
			},
			{ fieldname: "arn", fieldtype: "Data", label: __("ARN") },
			{ fieldtype: "Column Break" },
			{ fieldname: "valid_from", fieldtype: "Date", label: __("Valid From") },
			{ fieldname: "valid_upto", fieldtype: "Date", label: __("Valid Upto") },
			{ fieldtype: "Section Break", label: __("What do you do?") },
			check("claim_incentives", __("Duty Drawback, RoDTEP and Other Incentives"), exports),
			check("track_shipments", __("Shipment Tracking and Document Checklist"), exports),
			check("use_dgft_licences", __("DGFT Licences (Advance Authorisation, EPCG)")),
			check("use_trade_agreements", __("Trade Agreements (FTA Certificates of Origin)")),
			{ fieldtype: "Column Break" },
			check("do_merchant_export", __("Merchant Export (buying at 0.1% GST)"), exports),
			check(
				"ship_special_cargo",
				__("Dangerous Goods or Temperature-controlled Cargo"),
				exports
			),
			check("use_ecgc", __("ECGC Credit Cover"), exports),
		],
		primary_action_label: __("Set Up"),
		primary_action(values) {
			for (const df of dialog.fields) {
				if (df.fieldtype === "Check") values[df.fieldname] = values[df.fieldname] ? 1 : 0;
			}
			frappe
				.call({ method: `${METHOD}.run_setup`, args: { values }, freeze: true })
				.then(({ message }) => {
					dialog.hide();
					frappe.show_alert({
						message: __("Set up: {0}", [message.done.join(", ")]),
						indicator: "green",
					});
					setTimeout(() => window.location.reload(), 1500);
				});
		},
	});
	const load = () => {
		const company = dialog.get_value("company");
		if (!company) return;
		frappe
			.xcall(`${METHOD}.get_setup`, { company })
			.then((known) => dialog.set_values(known || {}));
	};
	dialog.show();
	load();
}
