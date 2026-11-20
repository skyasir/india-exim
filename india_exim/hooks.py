app_name = "india_exim"
app_title = "India EXIM"
app_publisher = "Yasir Shaikh"
app_description = (
	"Export-import compliance for Indian businesses on ERPNext: customs, DGFT, FEMA and trade documents"
)
app_email = "erp.yasirshaikh@gmail.com"
app_license = "gpl-3.0"
required_apps = ["frappe/erpnext", "resilient-tech/india_compliance"]
app_home = "/desk/india-exim"

add_to_apps_screen = [
	{
		"name": app_name,
		"logo": "/assets/india_exim/images/india-exim.svg",
		"title": app_title,
		"route": app_home,
	}
]

before_install = "india_exim.install.before_install"
after_install = "india_exim.install.after_install"
before_migrate = "india_exim.install.before_migrate"
after_migrate = "india_exim.install.after_migrate"
before_uninstall = "india_exim.install.before_uninstall"
before_tests = "india_exim.tests.before_tests"

app_include_css = "/assets/india_exim/css/exim_boards.css"

doctype_js = {
	"Company": "public/js/company.js",
	"Customer": "public/js/exim_flags.js",
	"Supplier": "public/js/exim_flags.js",
	"Quotation": ["public/js/exim_flags.js", "public/js/export_parties.js", "public/js/quotation.js"],
	"Sales Order": ["public/js/exim_flags.js", "public/js/export_parties.js"],
	"Delivery Note": ["public/js/exim_flags.js", "public/js/export_parties.js"],
	"Sales Invoice": [
		"public/js/exim_flags.js",
		"public/js/export_parties.js",
		"public/js/sales_invoice.js",
	],
	"Purchase Invoice": "public/js/exim_flags.js",
	"Bill of Entry": "public/js/bill_of_entry.js",
}

extend_doctype_class = {
	"Bill of Entry": ["india_exim.overrides.bill_of_entry.BillOfEntryEXIM"],
}

SETTLEMENT_EVENTS = {
	"on_submit": "india_exim.fema.payments.on_settlement_change",
	"on_cancel": "india_exim.fema.payments.on_settlement_change",
	"on_update_after_submit": "india_exim.fema.payments.on_settlement_change",
}

doc_events = {
	"Company": {
		"after_insert": "india_exim.overrides.company.after_insert",
	},
	"Item": {
		"validate": "india_exim.overrides.item.validate",
	},
	"Quotation": {
		"validate": [
			"india_exim.overrides.quotation.validate",
			"india_exim.controls.validate",
			"india_exim.utils.parties.fill_party_details",
		],
		"before_update_after_submit": "india_exim.utils.parties.fill_party_details",
	},
	"Sales Order": {
		"validate": [
			"india_exim.utils.parties.fill_party_details",
			"india_exim.controls.validate",
		],
		"before_update_after_submit": "india_exim.utils.parties.fill_party_details",
	},
	"Delivery Note": {
		"validate": [
			"india_exim.utils.export_details.fill_from_sales_order",
			"india_exim.utils.parties.fill_party_details",
		],
		"before_update_after_submit": "india_exim.utils.parties.fill_party_details",
	},
	"Sales Invoice": {
		"validate": [
			"india_exim.utils.export_details.fill_from_sales_order",
			"india_exim.overrides.sales_invoice.validate",
			"india_exim.controls.validate",
			"india_exim.utils.parties.fill_party_details",
		],
		"before_update_after_submit": "india_exim.utils.parties.fill_party_details",
		"on_submit": "india_exim.fema.payments.on_settlement_change",
		"on_cancel": "india_exim.fema.payments.on_settlement_change",
	},
	"Purchase Invoice": {
		"validate": [
			"india_exim.overrides.purchase_invoice.set_free_time_end",
			"india_exim.overrides.purchase_invoice.set_merchant_export_due",
		],
		"before_update_after_submit": [
			"india_exim.overrides.purchase_invoice.set_free_time_end",
			"india_exim.overrides.purchase_invoice.set_merchant_export_due",
		],
		"on_submit": "india_exim.fema.payments.on_settlement_change",
		"on_cancel": "india_exim.fema.payments.on_settlement_change",
	},
	"Payment Entry": SETTLEMENT_EVENTS,
	"Journal Entry": {
		**SETTLEMENT_EVENTS,
		"on_cancel": [
			"india_exim.fema.payments.on_settlement_change",
			"india_exim.export_incentives.accounting.on_journal_entry_cancel",
		],
	},
	"Bill of Entry": {
		"validate": "india_exim.dgft_licences.authorisation.validate_bill_of_entry",
		"on_submit": [
			"india_exim.overrides.bill_of_entry.on_submit",
			"india_exim.dgft_licences.authorisation.on_customs_document_change",
		],
		"before_cancel": "india_exim.overrides.bill_of_entry.before_cancel",
		"on_cancel": "india_exim.dgft_licences.authorisation.on_customs_document_change",
	},
}

export_python_type_annotations = True

scheduler_events = {
	"daily": [
		"india_exim.export_incentives.doctype.rodtep_scrip.rodtep_scrip.mark_expired_scrips",
		"india_exim.fema.payments.refresh_open_documents",
		"india_exim.alerts.send_daily_alerts",
		"india_exim.dgft_licences.authorisation.refresh_statuses",
	],
}
