"""The Imports tick is now the Business Type: a site that ticked it does both."""

import frappe
from frappe.utils import cint


def execute():
	# do_imports is no longer a field, so it is read from tabSingles
	does_imports = frappe.db.get_singles_dict("India EXIM Settings").get("do_imports")
	frappe.db.set_single_value(
		"India EXIM Settings", "business_type", "Both" if cint(does_imports) else "Export"
	)
