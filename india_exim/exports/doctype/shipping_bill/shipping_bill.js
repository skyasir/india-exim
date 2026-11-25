// Copyright (c) 2026, Yasir Shaikh and contributors
// For license information, please see license.txt

frappe.ui.form.on("Shipping Bill", {
	setup(frm) {
		frm.set_query("export_shipment", () => ({
			filters: {
				company: frm.doc.company,
				customer: frm.doc.customer,
				status: ["!=", "Cancelled"],
			},
		}));
		frm.set_query("sales_invoice", "items", () => ({
			filters: { company: frm.doc.company, customer: frm.doc.customer, docstatus: 1 },
		}));
	},

	onload(frm) {
		// Frappe fills a new Country link with the company's own, where an export never goes
		if (frm.is_new() && frm.doc.destination_country === frappe.boot.sysdefaults.country)
			frm.set_value("destination_country", "");
	},

	refresh(frm) {
		set_status_indicator(frm);
		if (frm.doc.docstatus === 1) {
			frm.add_custom_button(
				__("Evidence Pack"),
				() => download_evidence_pack(frm),
				__("View")
			);
		}
		const earned = frm.doc.total_drawback || frm.doc.total_rodtep || frm.doc.total_rosctl;
		if (
			frm.doc.docstatus === 1 &&
			frm.doc.leo_date &&
			earned &&
			frappe.model.can_create("Export Incentive Claim")
		) {
			frm.add_custom_button(
				__("Incentive Claims"),
				() => make_incentive_claims(frm),
				__("Create")
			);
		}
		if (frm.doc.docstatus === 1 && frm.doc.accrual_journal_entry) {
			frm.add_custom_button(
				__("Incentive Accrual"),
				() => frappe.set_route("Form", "Journal Entry", frm.doc.accrual_journal_entry),
				__("View")
			);
		}
	},

	get_items_from_invoices(frm) {
		if (!frm.doc.customer) {
			frappe.msgprint(__("Select the customer first."));
			return;
		}
		new frappe.ui.form.MultiSelectDialog({
			doctype: "Sales Invoice",
			target: frm,
			setters: { posting_date: null },
			add_filters_group: 1,
			get_query: () => ({
				filters: {
					company: frm.doc.company,
					customer: frm.doc.customer,
					docstatus: 1,
					is_return: 0,
				},
			}),
			action(selections) {
				if (!selections.length) return;
				frappe
					.call({
						method: "india_exim.exports.doctype.shipping_bill.shipping_bill.get_items_from_sales_invoices",
						args: { sales_invoices: selections },
					})
					.then(({ message }) => {
						const existing = new Set(
							(frm.doc.items || []).map((row) => row.sales_invoice_item)
						);
						(message || [])
							.filter((row) => !existing.has(row.sales_invoice_item))
							.forEach((row) => frm.add_child("items", row));
						frm.refresh_field("items");
						this.dialog.hide();
					});
			},
		});
	},
});

frappe.ui.form.on("Shipping Bill Item", {
	form_render: set_drawback_entries,
	customs_tariff_item: set_drawback_entries,
});

// the entries of the row's own heading, with what each one covers
function set_drawback_entries(frm, cdt, cdn) {
	const tariff = locals[cdt][cdn].customs_tariff_item;
	const field =
		frm.fields_dict.items.grid.get_row(cdn)?.grid_form?.fields_dict.drawback_serial_no;
	if (!field?.set_data) return;
	if (!tariff) return field.set_data([]);
	frappe
		.xcall("india_exim.exports.doctype.shipping_bill.shipping_bill.get_drawback_entries", {
			customs_tariff_item: tariff,
		})
		.then((options) => field.set_data(options || []));
}

function set_status_indicator(frm) {
	const colours = {
		Draft: "red",
		Filed: "blue",
		"LEO Granted": "orange",
		"EGM Filed": "green",
		Cancelled: "red",
	};
	if (frm.doc.status)
		frm.page.set_indicator(__(frm.doc.status), colours[frm.doc.status] || "gray");
}

// Drawback and RoDTEP / RoSCTL claims in one go, as drafts for the scroll numbers.
function make_incentive_claims(frm) {
	frappe
		.call({
			method: "india_exim.exports.doctype.shipping_bill.shipping_bill.make_incentive_claims",
			args: { shipping_bill: frm.doc.name },
			freeze: true,
		})
		.then(({ message: claims = [] }) => {
			if (claims.length === 1) {
				frappe.set_route("Form", "Export Incentive Claim", claims[0].name);
			} else if (claims.length) {
				frappe.set_route("List", "Export Incentive Claim", {
					name: ["in", claims.map((claim) => claim.name)],
				});
			}
		});
}

// One ZIP with every document, attachment, payment and change for an audit or enquiry.
function download_evidence_pack(frm) {
	const url = frappe.urllib.get_full_url(
		"/api/method/india_exim.utils.evidence_pack.download_evidence_pack?" +
			new URLSearchParams({ doctype: frm.doctype, name: frm.doc.name })
	);
	window.open(url);
}
