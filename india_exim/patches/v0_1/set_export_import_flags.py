import frappe

EXPORT_DOCTYPES = ("Customer", "Sales Order", "Sales Invoice")
IMPORT_DOCTYPES = ("Supplier", "Purchase Invoice")


def execute():
	"""Tick Is Export / Is Import on existing overseas parties and transactions."""
	from india_exim.install import setup_custom_fields

	setup_custom_fields()  # patches run before after_migrate creates the fields
	for doctypes, fieldname in ((EXPORT_DOCTYPES, "exim_is_export"), (IMPORT_DOCTYPES, "exim_is_import")):
		for doctype in doctypes:
			if frappe.db.has_column(doctype, fieldname) and frappe.db.has_column(doctype, "gst_category"):
				frappe.db.set_value(
					doctype, {"gst_category": "Overseas", fieldname: 0}, fieldname, 1, update_modified=False
				)
