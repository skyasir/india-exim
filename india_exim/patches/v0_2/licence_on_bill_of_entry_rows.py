"""The licence moved to each Bill of Entry row; bills entered before had it on the header only."""

import frappe

from india_exim.install import setup_custom_fields


def execute():
	setup_custom_fields()
	for row in frappe.get_all(
		"Bill of Entry",
		filters={"exim_authorisation": ("is", "set")},
		fields=["name", "exim_authorisation"],
	):
		frappe.db.set_value(
			"Bill of Entry Item",
			{"parent": row.name, "exim_authorisation": ("is", "not set")},
			"exim_authorisation",
			row.exim_authorisation,
			update_modified=False,
		)
