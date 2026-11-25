"""Fill the defaults of India EXIM Settings fields added after a site was installed.

Frappe applies a field's default only when the settings record is first created; a site that
already had India EXIM Settings would otherwise read 0 for buyer screening (which switches that
check off) and blank for the other new fields."""

import frappe

DEFAULTS = {
	"pre_shipment_checks": "Warn",
	"buyer_screening_months": 12,
	"merchant_export_days": 90,
	"scrip_validity_months": 24,
}


def execute():
	# "0" counts as unset too: these fields did not exist before, so a 0 can only be the blank value

	singles = frappe.qb.Table("tabSingles")
	saved = set(
		frappe.qb.from_(singles)
		.select(singles.field)
		.where(singles.doctype == "India EXIM Settings")
		.where(singles.field.isin(list(DEFAULTS)))
		.where(singles.value.isnotnull())
		.where(singles.value != "")
		.where(singles.value != "0")
		.run(pluck=True)
	)
	for field, value in DEFAULTS.items():
		if field not in saved:
			frappe.db.set_single_value("India EXIM Settings", field, value)
