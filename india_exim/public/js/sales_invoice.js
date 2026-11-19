frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		if (!frm.doc.exim_is_export) return;
		render_export_status(frm);
		if (frm.doc.docstatus !== 1 || frm.doc.is_return) return;

		frm.add_custom_button(
			__("Shipping Bill"),
			() =>
				frappe.model.open_mapped_doc({
					method: "india_exim.exports.doctype.shipping_bill.shipping_bill.make_shipping_bill",
					frm,
				}),
			__("Create")
		);
		frm.add_custom_button(
			__("Export Shipment"),
			() =>
				frappe.model.open_mapped_doc({
					method: "india_exim.overrides.sales_invoice.make_export_shipment",
					frm,
				}),
			__("Create")
		);
	},
});

function render_export_status(frm) {
	const wrapper = frm.get_field("exim_summary")?.$wrapper;
	if (!wrapper) return;
	if (frm.is_new()) {
		wrapper.html(`<p class="text-muted">${__("Save and submit the invoice to start the shipping bill.")}</p>`);
		return;
	}
	frappe
		.call({
			method: "india_exim.overrides.sales_invoice.get_export_status",
			args: { sales_invoice: frm.doc.name },
		})
		.then(({ message }) => {
			const { shipping_bills = [], shipments = [] } = message || {};
			const link = (doctype, name, label) =>
				`<a href="/desk/${frappe.router.slug(doctype)}/${encodeURIComponent(name)}">${frappe.utils.escape_html(label || name)}</a>`;
			const money = (value, currency) => format_currency(value || 0, currency);

			const bill_rows = shipping_bills
				.map(
					(sb) => `<tr>
						<td>${link("Shipping Bill", sb.name, sb.shipping_bill_number || sb.name)}</td>
						<td>${frappe.datetime.str_to_user(sb.shipping_bill_date) || ""}</td>
						<td>${__(sb.status)}${sb.leo_date ? ` · ${__("LEO")} ${frappe.datetime.str_to_user(sb.leo_date)}` : ""}</td>
						<td>${__(sb.realisation_status)} · ${money(sb.outstanding_value, sb.currency)} ${__("due by")} ${frappe.datetime.str_to_user(sb.realisation_due_date) || "-"}</td>
						<td>${money((sb.total_drawback || 0) + (sb.total_rodtep || 0), frappe.defaults.get_default("currency"))}</td>
					</tr>`
				)
				.join("");
			const shipment_rows = shipments
				.map(
					(s) => `<tr>
						<td>${link("Export Shipment", s.name)}</td>
						<td>${__(s.status)}</td>
						<td>${s.readiness_percent || 0}% ${__("documents ready")}</td>
						<td>${__("ETD")} ${frappe.datetime.str_to_user(s.etd) || "-"}</td>
						<td>${s.bl_number ? `${__("BL")} ${frappe.utils.escape_html(s.bl_number)}` : ""}</td>
					</tr>`
				)
				.join("");

			wrapper.html(`
				<table class="table table-bordered table-sm">
					<thead><tr><th>${__("Shipping Bill")}</th><th>${__("Date")}</th><th>${__("Customs")}</th><th>${__("Realisation")}</th><th>${__("Incentives")}</th></tr></thead>
					<tbody>${bill_rows || `<tr><td colspan="5" class="text-muted">${__("No shipping bill yet.")}</td></tr>`}</tbody>
				</table>
				<table class="table table-bordered table-sm">
					<thead><tr><th>${__("Export Shipment")}</th><th>${__("Status")}</th><th>${__("Documents")}</th><th>${__("Schedule")}</th><th>${__("Transport Document")}</th></tr></thead>
					<tbody>${shipment_rows || `<tr><td colspan="5" class="text-muted">${__("No shipment yet.")}</td></tr>`}</tbody>
				</table>`);
		});
}
