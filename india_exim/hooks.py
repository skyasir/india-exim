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

doctype_js = {
	"Company": "public/js/company.js",
	"Sales Invoice": "public/js/sales_invoice.js",
}

doc_events = {
	"Company": {
		"after_insert": "india_exim.overrides.company.after_insert",
	},
	"Item": {
		"validate": "india_exim.overrides.item.validate",
	},
	"Sales Invoice": {
		"validate": "india_exim.overrides.sales_invoice.validate",
	},
}

export_python_type_annotations = True

scheduler_events = {
	"daily": [
		"india_exim.export_incentives.doctype.rodtep_scrip.rodtep_scrip.mark_expired_scrips",
	],
}
