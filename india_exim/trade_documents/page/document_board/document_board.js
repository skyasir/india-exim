// Document Board: the checklist rows of every open shipment, in columns by status.
// Drag a card to another column, or use its buttons, to change the status or attach the file.
// Data: india_exim.api.shipments. Every change is saved through the Export Shipment.
frappe.pages["document-board"].on_page_load = (wrapper) => {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Document Board"),
		single_column: true,
	});
	new DocumentBoard(page);
};

const COLUMN_STATUS = {
	Pending: "Pending",
	Applied: "Applied",
	Received: "Received",
	Sent: "Sent",
	Discrepancy: "Discrepancy",
};

class DocumentBoard {
	constructor(page) {
		this.page = page;
		this.company = page.add_field({
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			change: () => this.refresh(),
		});
		this.customer = page.add_field({
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
			change: () => this.refresh(),
		});
		this.responsible = page.add_field({
			fieldname: "responsible",
			label: __("Responsible"),
			fieldtype: "Link",
			options: "User",
			change: () => this.refresh(),
		});
		page.add_field({
			fieldname: "mine",
			label: __("Assigned to Me"),
			fieldtype: "Check",
			change: (e) => {
				this.responsible.set_value(e.target.checked ? frappe.session.user : "");
			},
		});
		page.set_secondary_action(__("Refresh"), () => this.refresh());
		page.add_menu_item(__("Shipment Control Tower"), () =>
			frappe.set_route("shipment-control-tower")
		);
		page.add_menu_item(__("Pending Trade Documents Report"), () =>
			frappe.set_route("query-report", "Pending Trade Documents")
		);
		this.$body = $(`<div class="exim-board"></div>`).appendTo(page.main);
		this.refresh();
	}

	refresh() {
		frappe
			.call("india_exim.api.shipments.get_document_board", {
				company: this.company.get_value() || null,
				customer: this.customer.get_value() || null,
				responsible: this.responsible.get_value() || null,
			})
			.then(({ message }) => this.render(message.columns));
	}

	render(columns) {
		const e = frappe.utils.escape_html;
		this.rows = {};
		const html = columns
			.map(
				(column) => `<div class="exim-column" data-status="${column.status}">
				<div class="exim-column-head">${__(column.status)} <span class="exim-count">${
					column.rows.length
				}</span></div>
				${column.rows
					.map((row) => {
						this.rows[row.name] = row;
						return `<div class="exim-card" draggable="true" data-row="${e(row.name)}">
						<div class="exim-card-title">${e(row.document_type)}</div>
						<div class="exim-line"><a href="/desk/export-shipment/${encodeURIComponent(row.shipment)}">${e(
							row.shipment
						)}</a> · ${e(row.customer_name || "")}</div>
						${
							row.due_date
								? `<div class="exim-line ${
										row.overdue ? "exim-urgent" : "text-muted"
								  }">${__("Due")} ${frappe.datetime.str_to_user(
										row.due_date
								  )}</div>`
								: ""
						}
						${
							row.document_number
								? `<div class="exim-line text-muted">${__("No.")} ${e(
										row.document_number
								  )}</div>`
								: ""
						}
						${
							row.responsible
								? `<div class="exim-line text-muted">${e(
										frappe.user.full_name(row.responsible)
								  )}</div>`
								: ""
						}
						${row.mandatory ? "" : `<span class="exim-chip">${__("Optional")}</span>`}
						<div class="exim-card-actions">
							${
								row.attachment
									? `<a class="btn btn-xs btn-default" href="${encodeURI(
											row.attachment
									  )}" target="_blank">${__("View File")}</a>`
									: ""
							}
							<button class="btn btn-xs btn-default exim-attach">${__("Attach")}</button>
							<button class="btn btn-xs btn-default exim-move">${__("Move")}</button>
						</div>
					</div>`;
					})
					.join("")}
			</div>`
			)
			.join("");
		this.$body.html(`<div class="exim-columns">${html}</div>`);
		this.bind();
	}

	bind() {
		const self = this;
		this.$body.find(".exim-card").on("dragstart", function (ev) {
			ev.originalEvent.dataTransfer.setData("text/plain", $(this).data("row"));
		});
		this.$body
			.find(".exim-column")
			.on("dragover", function (ev) {
				ev.preventDefault();
				$(this).addClass("exim-drop");
			})
			.on("dragleave drop", function () {
				$(this).removeClass("exim-drop");
			})
			.on("drop", function (ev) {
				ev.preventDefault();
				const row = self.rows[ev.originalEvent.dataTransfer.getData("text/plain")];
				const status = COLUMN_STATUS[$(this).data("status")];
				if (!row || !status || status === row.status) return;
				// the certificate number is known when the document arrives
				if (status === "Received" && !row.document_number) self.move(row, status);
				else self.update(row, { status });
			});
		this.$body.find(".exim-move").on("click", function () {
			const row = self.rows[$(this).closest(".exim-card").data("row")];
			self.move(row, row.status);
		});
		this.$body.find(".exim-attach").on("click", function () {
			const row = self.rows[$(this).closest(".exim-card").data("row")];
			new frappe.ui.FileUploader({
				doctype: "Export Shipment",
				docname: row.shipment,
				folder: "Home/Attachments",
				on_success: (file) =>
					self.update(row, {
						attachment: file.file_url,
						status: row.status === "Pending" ? "Received" : null,
					}),
			});
		});
	}

	move(row, status) {
		frappe.prompt(
			[
				{
					fieldname: "status",
					label: __("Status"),
					fieldtype: "Select",
					reqd: 1,
					default: status,
					options: [
						"Pending",
						"Applied",
						"Received",
						"Checked",
						"Sent",
						"Accepted",
						"Discrepancy",
						"Not Required",
					],
				},
				{
					fieldname: "document_number",
					label: __("Document No."),
					fieldtype: "Data",
					default: row.document_number,
					description: __("Printed on the bank covering letter."),
				},
				{
					fieldname: "document_date",
					label: __("Document Date"),
					fieldtype: "Date",
					default: row.document_date,
				},
			],
			(values) => this.update(row, values),
			__("Move {0}", [row.document_type])
		);
	}

	update(row, values) {
		frappe
			.call({
				method: "india_exim.api.shipments.update_document",
				args: { shipment: row.shipment, row: row.name, ...values },
				freeze: true,
			})
			.then(({ message }) => {
				frappe.show_alert({
					message: __("{0}: {1}% documents ready", [
						row.shipment,
						Math.round(message.readiness_percent),
					]),
					indicator: "green",
				});
				this.refresh();
			});
	}
}
