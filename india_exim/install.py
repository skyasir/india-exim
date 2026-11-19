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


def delete_custom_fields():
	for doctype, fields in CUSTOM_FIELDS.items():
		frappe.db.delete(
			"Custom Field",
			{"dt": doctype, "fieldname": ("in", [field["fieldname"] for field in fields])},
		)
		frappe.clear_cache(doctype=doctype)
