/* global india_exim */
// Item > Export & Import tab: the tariff's trade policy, and its incentive and duty rates
// (see exim_rates.js), kept per tariff code since the law sets them that way.
frappe.ui.form.on("Item", {
	refresh: render_tariff,
	exim_customs_tariff_item: render_tariff,
	gst_hsn_code: set_tariff_from_hsn,
	exim_drawback_serial_no: render_tariff,
	exim_package_length: set_package_volume,
	exim_package_width: set_package_volume,
	exim_package_height: set_package_volume,
});

function render_tariff(frm) {
	render_tariff_summary(frm);
	india_exim.rates.render_incentives(frm);
	india_exim.rates.render_duty(frm);
}

function set_tariff_from_hsn(frm) {
	// an 8-digit GST HSN code is the ITC-HS code; India EXIM's tariff data has the tariff items
	const hsn = frm.doc.gst_hsn_code;
	if (frm.doc.exim_customs_tariff_item || !hsn || hsn.length !== 8) return;
	frappe.db.exists("Customs Tariff Item", hsn).then((exists) => {
		if (exists) {
			frm.set_value("exim_customs_tariff_item", hsn);
		} else {
			// created from the GST HSN master when the item is saved
			frm.get_field("exim_tariff_summary").$wrapper.html(
				`<p class="text-muted small">${__(
					"The tariff item {0} is created from the GST HSN code when you save.",
					[hsn]
				)}</p>`
			);
		}
	});
}

function set_package_volume(frm) {
	const { exim_package_length: l, exim_package_width: w, exim_package_height: h } = frm.doc;
	frm.set_value("exim_package_volume", l && w && h ? (l * w * h) / 1000000 : 0);
}

function render_tariff_summary(frm) {
	const field = frm.get_field("exim_tariff_summary");
	if (!field) return;
	const tariff = frm.doc.exim_customs_tariff_item;
	if (!tariff) {
		field.$wrapper.html(
			`<p class="text-muted small">${__(
				"Set the ITC-HS Code to see its policy and rates."
			)}</p>`
		);
		return;
	}
	frappe
		.xcall("india_exim.overrides.item.get_tariff_summary", {
			customs_tariff_item: tariff,
			drawback_serial_no: frm.doc.exim_drawback_serial_no || null,
		})
		.then((data) => {
			frm.fields_dict.exim_drawback_serial_no?.set_data?.(data?.drawback_serials || []);
			if (!data || !Object.keys(data).length) {
				field.$wrapper.empty();
				return;
			}
			// the ticks and serial number only matter when there is a choice to make
			frm.toggle_display(
				"exim_drawback_serial_no",
				cint(frm.doc.exim_claim_drawback) &&
					((data?.drawback_serials || []).length > 1 ||
						Boolean(frm.doc.exim_drawback_serial_no))
			);
			const esc = frappe.utils.escape_html;
			const policy = (label, value) =>
				frappe.ui.badge.html({
					label: `${label}: ${value ? __(value) : __("not checked")}`,
					theme: !value
						? "gray"
						: { Free: "green", Prohibited: "red" }[value] || "orange",
				});
			const badges = [
				policy(__("Export"), data.export_policy),
				policy(__("Import"), data.import_policy),
			];
			if (data.uqc)
				badges.push(frappe.ui.badge.html({ label: `${__("Unit")}: ${data.uqc}` }));
			if (data.is_scomet)
				badges.push(
					frappe.ui.badge.html({
						label: __("SCOMET: authorisation needed"),
						theme: "red",
					})
				);
			field.$wrapper.html(`
				<div class="small">
					<div class="text-muted" style="margin-bottom: 8px">${esc(
						frappe.ellipsis(data.description || "", 160)
					)}</div>
					<div style="display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px">${badges.join("")}</div>
					<a href="${frappe.utils.get_form_link("Customs Tariff Item", tariff)}">${__(
				"Open the tariff item"
			)}</a>
				</div>`);
		});
}
