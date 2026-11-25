"""RBI periods become dated rows (export realisation 9 -> 15 months and shipment against advance
12 -> 36 months from 14.11.2025). Fill the rows and recompute the due dates of open documents."""

import frappe

from india_exim.fema.payments import update_bill_of_entry_payment, update_shipping_bill_realisation
from india_exim.fema.periods import set_default_periods


def execute():
	frappe.reload_doc("exim_setup", "doctype", "fema_period")
	frappe.reload_doc("exim_setup", "doctype", "india_exim_settings")
	set_default_periods()

	for name in frappe.get_all(
		"Shipping Bill",
		filters={"docstatus": 1, "realisation_status": ("!=", "Not Required")},
		pluck="name",
	):
		update_shipping_bill_realisation(name)

	for name in frappe.get_all(
		"Bill of Entry", filters={"docstatus": 1, "exim_payment_status": ("!=", "Paid")}, pluck="name"
	):
		update_bill_of_entry_payment(name)
