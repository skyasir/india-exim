import click
import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from india_exim.setup.accounts import setup_exim_accounts
from india_exim.setup.custom_fields import CUSTOM_FIELDS
from india_exim.setup.seed import seed_master_data

ROLES = ("EXIM Manager", "EXIM User")


def before_install():
	create_roles()


def after_install():
	try:
		setup_custom_fields()
		for company in frappe.get_all("Company", pluck="name"):
			setup_exim_accounts(company)
		seed_master_data()
		enable_proforma_invoice()
	except Exception:
		click.secho(
			"India EXIM installation failed. Please re-run the install or report the issue.", fg="red"
		)
		raise


def before_migrate():
	create_roles()


def after_migrate():
	setup_custom_fields()
	seed_master_data()


def enable_proforma_invoice():
	"""Turn on ERPNext's Proforma Invoice (made from a submitted Sales Order) with the Export
	Proforma Invoice as its print format, unless a format is already chosen. Run once, so a
	user who turns the feature off keeps it off."""
	settings = frappe.get_single("Selling Settings")
	if not settings.meta.has_field("enable_proforma_invoice"):
		return
	settings.enable_proforma_invoice = 1
	if not settings.default_proforma_print_format and frappe.db.exists(
		"Print Format", "Export Proforma Invoice"
	):
		settings.default_proforma_print_format = "Export Proforma Invoice"
	settings.flags.ignore_permissions = True
	settings.save()


def before_uninstall():
	delete_custom_fields()


def create_roles():
	for role in ROLES:
		if frappe.db.exists("Role", role):
			continue
		frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
			ignore_permissions=True
		)


def setup_custom_fields():
	create_custom_fields(CUSTOM_FIELDS, ignore_validate=True)
	delete_stale_custom_fields()


def delete_stale_custom_fields():
	"""Remove exim_ fields an older version created but the current definition no longer has."""
	for doctype, fields in CUSTOM_FIELDS.items():
		current = [field["fieldname"] for field in fields]
		stale = frappe.get_all(
			"Custom Field",
			filters={
				"dt": doctype,
				"fieldname": ("like", "exim\\_%"),
				"name": ("not in", [f"{doctype}-{name}" for name in current]),
			},
			pluck="name",
		)
		for name in stale:
			frappe.delete_doc("Custom Field", name, ignore_permissions=True)
		if stale:
			frappe.clear_cache(doctype=doctype)


def delete_custom_fields():
	for doctype, fields in CUSTOM_FIELDS.items():
		frappe.db.delete(
			"Custom Field",
			{"dt": doctype, "fieldname": ("in", [field["fieldname"] for field in fields])},
		)
		frappe.clear_cache(doctype=doctype)
