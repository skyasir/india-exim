// Shipment Control Tower: every open export shipment as a card, in columns by stage.
// Data: india_exim.api.shipments.get_control_tower. Changes are made on the shipment itself.
frappe.pages["shipment-control-tower"].on_page_load = (wrapper) => {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Shipment Control Tower"), single_column: true });
	new ControlTower(page);
};

class ControlTower {
	constructor(page) {
		this.page = page;
		this.company = page.add_field({
			fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company",
			default: frappe.defaults.get_user_default("Company"), change: () => this.refresh(),
		});
		this.customer = page.add_field({
			fieldname: "customer", label: __("Customer"), fieldtype: "Link", options: "Customer", change: () => this.refresh(),
		});
		page.set_primary_action(__("New Shipment"), () => frappe.new_doc("Export Shipment"), "add");
		page.set_secondary_action(__("Refresh"), () => this.refresh());
		page.add_menu_item(__("Document Board"), () => frappe.set_route("document-board"));
		page.add_menu_item(__("Shipment Tracker Report"), () => frappe.set_route("query-report", "Shipment Tracker"));
		this.$body = $(`<div class="exim-tower"></div>`).appendTo(page.main);
		this.refresh();
		frappe.realtime.on("list_update", (data) => {
			if (["Export Shipment", "Shipping Bill"].includes(data?.doctype) && frappe.get_route()[0] === "shipment-control-tower") {
				this.refresh();
			}
		});
	}

	refresh() {
		frappe
			.call("india_exim.api.shipments.get_control_tower", {
				company: this.company.get_value() || null,
				customer: this.customer.get_value() || null,
			})
			.then(({ message }) => this.render(message));
	}

	render({ stages, shipments }) {
		if (!shipments.length) {
			this.$body.html(`<div class="exim-empty">${__("No open export shipments.")}
				<a href="/desk/export-shipment/new">${__("Create one")}</a></div>`);
			return;
		}
		const columns = stages
			.map((stage) => {
				const cards = shipments.filter((s) => s.status === stage);
				return `<div class="exim-column">
					<div class="exim-column-head">${__(stage)} <span class="exim-count">${cards.length}</span></div>
					${cards.map((s) => this.card(s)).join("")}
				</div>`;
			})
			.join("");
		this.$body.html(`<div class="exim-columns">${columns}</div>`);
		this.$body.find(".exim-card").on("click", (e) => {
			if ($(e.target).closest("a").length) return;
			frappe.set_route("Form", "Export Shipment", $(e.currentTarget).data("name"));
		});
	}

	card(s) {
		const e = frappe.utils.escape_html;
		const readiness = Math.round(s.readiness_percent || 0);
		const bar = readiness >= 100 ? "green" : readiness >= 50 ? "orange" : "red";
		const cutoff = s.next_cutoff
			? `<div class="exim-line ${s.next_cutoff.hours <= 48 ? "exim-urgent" : ""}">
				${frappe.utils.icon("clock", "xs")} ${e(s.next_cutoff.label)} ${__("cut-off in")} ${this.duration(s.next_cutoff.hours)}</div>`
			: "";
		const docs = s.pending_documents
			.slice(0, 4)
			.map((d) => `<span class="exim-chip ${d.overdue ? "exim-chip-red" : ""}">${e(d.document_type)}</span>`)
			.join("");
		const more = s.pending_documents.length > 4 ? `<span class="exim-chip">+${s.pending_documents.length - 4}</span>` : "";
		const bills = s.shipping_bills
			.map(
				(b) => `<div class="exim-line"><a href="/desk/shipping-bill/${encodeURIComponent(b.name)}">${__("SB")} ${e(b.shipping_bill_number || b.name)}</a>
					· ${__(b.status)} · ${__(b.realisation_status || "")}</div>`
			)
			.join("");
		return `<div class="exim-card" data-name="${e(s.name)}">
			<div class="exim-card-title">${e(s.customer_name || s.customer)}</div>
			<div class="exim-line text-muted">${e(s.name)} · ${e(s.destination_country || "")} · ${e(s.mode_of_transport || "")}</div>
			<div class="exim-line">${__("ETD")} ${frappe.datetime.str_to_user(s.etd) || "–"} · ${__("ETA")} ${frappe.datetime.str_to_user(s.eta) || "–"}</div>
			${s.vessel_voyage ? `<div class="exim-line text-muted">${e(s.vessel_voyage)}</div>` : ""}
			${cutoff}
			<div class="exim-progress"><div class="exim-progress-bar exim-${bar}" style="width:${Math.min(readiness, 100)}%"></div></div>
			<div class="exim-line text-muted">${__("{0}% documents ready", [readiness])}</div>
			${docs || more ? `<div class="exim-chips">${docs}${more}</div>` : ""}
			${bills}
			${s.bl_number ? `<div class="exim-line">${__("BL")} ${e(s.bl_number)}</div>` : ""}
		</div>`;
	}

	duration(hours) {
		return hours >= 48 ? __("{0} days", [Math.floor(hours / 24)]) : __("{0} h", [hours]);
	}
}
