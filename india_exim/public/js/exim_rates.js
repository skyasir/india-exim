/* global india_exim */
// Incentive and import duty rates on the Item, in ERPNext's Item Prices layout, and the dialogs to
// add them. They are kept on the tariff code. See india_exim/utils/item_rates.py.
frappe.provide("india_exim.rates");

(() => {
	const API = "india_exim.utils.item_rates";
	const pct = (value) => `${flt(value, 4)}%`;
	const date = (value) => (value ? frappe.datetime.str_to_user(value) : "");
	const validity = (row) =>
		row.effective_to
			? `${date(row.effective_from)} ${__("to")} ${date(row.effective_to)}`
			: `${__("From")} ${date(row.effective_from)}`;
	const esc = (value) => frappe.utils.escape_html(value || "");
	const per = (amount, uom) => `${format_currency(amount, "INR")} / ${esc(uom || __("unit"))}`;

	const embed = (frm, fieldname, options) => {
		const wrapper = frm.get_field(fieldname)?.$wrapper;
		if (!wrapper) return;
		// a quick second refresh must not leave two lists behind
		frappe.require("embedded_list.bundle.js", () => {
			wrapper.empty();
			const list = new frappe.ui.EmbeddedList({
				wrapper: $("<div></div>").appendTo(wrapper),
				show_index: true,
				show_search: false,
				...options,
				// the standard empty state is a tall box; one line is enough inside a form
				toggle_result_area() {
					const empty = !this.data.length;
					this.$result.toggle(!empty);
					this.$no_result.hide();
					wrapper.find(".exim-no-rates").remove();
					if (empty) {
						$(`<p class="exim-no-rates text-muted small"></p>`)
							.text(options.empty_message)
							.appendTo(wrapper);
					}
				},
			});
			list.refresh();
		});
	};

	const no_tariff = (frm, fieldname) =>
		frm
			.get_field(fieldname)
			?.$wrapper.html(`<p class="text-muted small">${__("Set the ITC-HS Code first.")}</p>`);

	india_exim.rates.render_incentives = (frm) => {
		const tariff = frm.doc.exim_customs_tariff_item;
		if (!frappe.model.can_read("Export Incentive Rate")) {
			frm.toggle_display("exim_incentive_rates", false);
			return;
		}
		if (!tariff) return no_tariff(frm, "exim_incentive_rates");
		embed(frm, "exim_incentive_rates", {
			description: __("Rates in force for ITC-HS {0}.", [tariff]),
			empty_message: ["61", "62", "63"].includes(tariff.slice(0, 2))
				? __(
						"No rates yet. Garments and made-ups (chapters 61 to 63) usually come under RoSCTL instead of RoDTEP. Add the RoSCTL and drawback rates."
				  )
				: __("No rates yet. Add the drawback or RoDTEP rate if you claim it."),
			add_button: frappe.model.can_create("Export Incentive Rate") && {
				label: __("Add Rate"),
				action: () => india_exim.rates.add_incentive(frm),
			},
			on_row_click: (row) => frappe.set_route("Form", "Export Incentive Rate", row.name),
			get_data: () =>
				frappe.xcall(`${API}.get_incentive_rates`, {
					customs_tariff_item: tariff,
					item_code: frm.is_new() ? null : frm.doc.name,
					drawback_serial_no: frm.doc.exim_drawback_serial_no || null,
				}),
			columns: [
				{ label: __("Scheme"), type: "badge", fieldname: "scheme" },
				{
					label: __("Applies To"),
					render: (row) =>
						row.item_code
							? __("This item only")
							: row.schedule_serial_no
							? `${__("Sr.")} ${esc(row.schedule_serial_no)}`
							: __("ITC-HS code"),
				},
				{
					label: __("Rate"),
					render: (row) => {
						if (row.scheme === "RoSCTL")
							return `${__("State")} ${pct(row.rate)} + ${__("Central")} ${pct(
								row.central_rate
							)}`;
						const rate = row.amount_per_unit
							? per(row.amount_per_unit, row.cap_uom)
							: pct(row.rate);
						return row.notified
							? `${rate}<div class="text-warning small">${__("Notified: {0}", [
									esc(row.notified),
							  ])}</div>`
							: rate;
					},
				},
				{
					label: __("Cap"),
					render: (row) =>
						[row.cap_per_unit, row.central_cap_per_unit]
							.filter(Boolean)
							.map((cap) => per(cap, row.cap_uom))
							.join(" + "),
				},
				{ label: __("Valid"), render: validity },
				{
					label: __("Source"),
					render: (row) => (row.data_source ? __("Official") : __("Manual")),
				},
			],
		});
	};

	india_exim.rates.render_duty = (frm) => {
		const tariff = frm.doc.exim_customs_tariff_item;
		if (!frappe.model.can_read("Customs Tariff Item")) {
			frm.toggle_display("exim_duty_rates", false);
			return;
		}
		if (!tariff) return no_tariff(frm, "exim_duty_rates");
		embed(frm, "exim_duty_rates", {
			description: __("Used on Bills of Entry. Leave empty if you only export."),
			empty_message: __("No rates yet."),
			add_button: frappe.model.can_write("Customs Tariff Item") && {
				label: __("Add Duty Rate"),
				action: () =>
					india_exim.rates.add_duty(tariff, () => india_exim.rates.render_duty(frm)),
			},
			on_row_click: () => frappe.set_route("Form", "Customs Tariff Item", tariff),
			get_data: () => frappe.xcall(`${API}.get_duty_rates`, { customs_tariff_item: tariff }),
			columns: [
				{ label: __("BCD"), render: (row) => pct(row.bcd_rate) },
				{ label: __("SWS (of BCD)"), render: (row) => pct(row.sws_rate) },
				{ label: __("AIDC"), render: (row) => pct(row.aidc_rate) },
				{ label: __("Other Duty"), render: (row) => pct(row.other_duty_rate) },
				{ label: __("Valid"), render: validity },
				{ label: __("Notification"), fieldname: "notification" },
			],
		});
	};

	india_exim.rates.add_incentive = (frm) => {
		const tariff = frm.doc.exim_customs_tariff_item;
		const drawback = "eval:doc.scheme == 'Duty Drawback'";
		const rosctl = "eval:doc.scheme == 'RoSCTL'";
		const dialog = new frappe.ui.Dialog({
			title: __("Add Incentive Rate for {0}", [tariff]),
			fields: [
				{
					fieldname: "scheme",
					fieldtype: "Select",
					label: __("Scheme"),
					options: ["Duty Drawback", "RoDTEP", "RoSCTL"],
					default: "Duty Drawback",
					reqd: 1,
				},
				{
					fieldname: "rate",
					fieldtype: "Percent",
					label: __("Rate % of FOB"),
					description: __("For RoSCTL, the State rate."),
				},
				{
					fieldname: "central_rate",
					fieldtype: "Percent",
					label: __("Central Rate % of FOB"),
					depends_on: rosctl,
				},
				{
					fieldname: "amount_per_unit",
					fieldtype: "Currency",
					options: "INR",
					label: __("Or Fixed Amount Per Unit (INR)"),
				},
				{
					fieldname: "effective_from",
					fieldtype: "Date",
					label: __("Effective From"),
					default: "Today",
					reqd: 1,
				},
				{ fieldtype: "Column Break" },
				{
					fieldname: "cap_per_unit",
					fieldtype: "Currency",
					options: "INR",
					label: __("Cap Per Unit (INR)"),
				},
				{
					fieldname: "central_cap_per_unit",
					fieldtype: "Currency",
					options: "INR",
					label: __("Central Cap Per Unit (INR)"),
					depends_on: rosctl,
				},
				{
					fieldname: "cap_uom",
					fieldtype: "Link",
					options: "UOM",
					label: __("Unit"),
					default: frm.doc.exim_uqc || frm.doc.stock_uom,
					depends_on: "eval:doc.cap_per_unit || doc.amount_per_unit",
					mandatory_depends_on: "cap_per_unit",
				},
				{
					fieldname: "schedule_serial_no",
					fieldtype: "Data",
					label: __("Schedule Serial No."),
					depends_on: "eval:doc.scheme != 'RoDTEP' && !doc.only_this_item",
				},
				{ fieldname: "notification", fieldtype: "Data", label: __("Notification No.") },
				{ fieldtype: "Section Break" },
				{
					fieldname: "only_this_item",
					fieldtype: "Check",
					label: __("Only for this item (Brand Rate fixed by Customs)"),
					depends_on: frm.is_new() ? "eval:false" : drawback,
				},
			],
			primary_action_label: __("Add"),
			primary_action(values) {
				const only = values.scheme === "Duty Drawback" && values.only_this_item ? 1 : 0;
				if (only) {
					values.item_code = frm.doc.name;
					values.schedule_serial_no = null;
				}
				values.only_this_item = only;
				const save = () =>
					frappe
						.call({
							method: `${API}.add_incentive_rate`,
							args: { customs_tariff_item: tariff, values },
							freeze: true,
						})
						.then(() => {
							dialog.hide();
							frm.trigger("exim_customs_tariff_item");
						});
				if (only) return save();
				confirm_others(tariff, frm.is_new() ? null : frm.doc.name, save);
			},
		});
		dialog.show();
	};

	const confirm_others = (customs_tariff_item, item_code, proceed) =>
		frappe
			.xcall(`${API}.count_other_items`, { customs_tariff_item, item_code })
			.then((count) =>
				count
					? frappe.confirm(
							__(
								"This rate also applies to {0} other item(s) with ITC-HS {1}. Add it?",
								[count, customs_tariff_item]
							),
							proceed
					  )
					: proceed()
			);

	india_exim.rates.add_duty = (tariff, done, effective_from) => {
		const dialog = new frappe.ui.Dialog({
			title: __("Add Import Duty Rate for {0}", [tariff]),
			fields: [
				{ fieldname: "bcd_rate", fieldtype: "Percent", label: __("BCD %") },
				{
					fieldname: "sws_rate",
					fieldtype: "Percent",
					label: __("SWS % of BCD"),
					default: 10,
				},
				{
					fieldname: "effective_from",
					fieldtype: "Date",
					label: __("Effective From"),
					default: effective_from || "Today",
					reqd: 1,
				},
				{ fieldtype: "Column Break" },
				{ fieldname: "aidc_rate", fieldtype: "Percent", label: __("AIDC %") },
				{
					fieldname: "other_duty_rate",
					fieldtype: "Percent",
					label: __("Other Duty % (ADD / Safeguard)"),
				},
				{ fieldname: "notification", fieldtype: "Data", label: __("Notification No.") },
			],
			primary_action_label: __("Add"),
			primary_action(values) {
				frappe
					.call({
						method: `${API}.add_duty_rate`,
						args: { customs_tariff_item: tariff, values },
						freeze: true,
					})
					.then(() => {
						dialog.hide();
						done();
					});
			},
		});
		dialog.show();
	};
})();
