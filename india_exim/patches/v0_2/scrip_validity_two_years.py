"""RoDTEP e-scrips are valid for two years (Notification 79/2022-Customs (N.T.), 15 Sept 2022); the app
used one. Scrips still carrying the one-year default are extended; dates a user typed are kept."""

import frappe
from frappe.utils import add_months, getdate


def execute():
	if frappe.db.get_single_value("India EXIM Settings", "scrip_validity_months") == 12:
		frappe.db.set_single_value("India EXIM Settings", "scrip_validity_months", 24)

	for row in frappe.get_all(
		"RoDTEP Scrip",
		filters={"docstatus": ("<", 2)},
		fields=["name", "docstatus", "scrip_date", "valid_upto", "status", "utilised_amount"],
	):
		if getdate(row.valid_upto) != getdate(add_months(row.scrip_date, 12)):
			continue
		values = {"valid_upto": add_months(row.scrip_date, 24)}
		if row.status == "Expired" and getdate(values["valid_upto"]) >= getdate():
			values["status"] = "Partly Used" if row.utilised_amount else "Active"
		frappe.db.set_value("RoDTEP Scrip", row.name, values)
