"""RBI periods (export realisation, shipment against advance, import payment) by date.

RBI changes these periods by regulation from a date, so each period is a dated row in India EXIM
Settings and a document takes the row in force on its own date. A later change does not move the
due dates of older documents.
"""

import frappe
from frappe.utils import add_months, getdate

EXPORT_REALISATION = "Export Realisation"
ADVANCE_SHIPMENT = "Shipment Against Advance"
IMPORT_PAYMENT = "Import Payment"

# Shipped with the app and used when the settings hold no row for a date
DEFAULT_PERIODS = (
	(EXPORT_REALISATION, "2000-01-01", 9),
	# FEM (Export of Goods and Services) (Second Amendment) Regulations, 2025, from 14.11.2025
	(EXPORT_REALISATION, "2025-11-14", 15),
	(ADVANCE_SHIPMENT, "2000-01-01", 12),
	(ADVANCE_SHIPMENT, "2025-11-14", 36),
	(IMPORT_PAYMENT, "2000-01-01", 6),
)


def get_periods() -> list[frappe._dict]:
	rows = frappe.get_all(
		"FEMA Period",
		filters={"parent": "India EXIM Settings", "parenttype": "India EXIM Settings"},
		fields=["period_for", "effective_from", "months"],
	)
	return rows or [
		frappe._dict(period_for=kind, effective_from=getdate(start), months=months)
		for kind, start, months in DEFAULT_PERIODS
	]


def get_months(period_for: str, on_date) -> int:
	"""Months allowed for a document dated on_date."""
	on_date = getdate(on_date)
	applicable = [
		row
		for row in get_periods()
		if row.period_for == period_for and getdate(row.effective_from) <= on_date and row.months
	]
	if not applicable:
		applicable = [
			frappe._dict(effective_from=getdate(start), months=months)
			for kind, start, months in DEFAULT_PERIODS
			if kind == period_for and getdate(start) <= on_date
		]
	return max(applicable, key=lambda row: getdate(row.effective_from)).months


def get_due_date(period_for: str, on_date):
	return add_months(on_date, get_months(period_for, on_date))


def set_default_periods() -> None:
	"""Fill the periods once, on install or when the table is still empty."""
	if frappe.db.exists("FEMA Period", {"parenttype": "India EXIM Settings"}):
		return
	settings = frappe.get_single("India EXIM Settings")
	for kind, start, months in DEFAULT_PERIODS:
		settings.append("fema_periods", {"period_for": kind, "effective_from": start, "months": months})
	settings.flags.ignore_permissions = True
	settings.flags.ignore_mandatory = True
	settings.save()
