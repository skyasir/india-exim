"""Feature switches are new: sites already using India EXIM keep everything visible."""

import frappe

from india_exim.features import FEATURES


def execute():
	for field in FEATURES:
		if field == "track_shipments":
			continue  # came later: enable_shipment_tracking
		frappe.db.set_single_value("India EXIM Settings", field, 1)

	# replaced by the Quick Setup step
	for step in (
		"EXIM Company Details",
		"EXIM AD Code",
		"EXIM Letter of Undertaking",
		"EXIM Tariff Item",
		"EXIM Incentive Rate",
		"EXIM Settings",
	):
		if frappe.db.exists("Onboarding Step", step):
			frappe.db.delete("Onboarding Step Map", {"step": step})
			frappe.delete_doc("Onboarding Step", step, ignore_permissions=True, force=True)
