import frappe
from frappe.model.utils.rename_field import rename_field

OLD_FIELDS = (
	"country",
	"country_group",
	"tariff_prefixes",
	"item_group",
	"incoterm",
	"payment_terms_type",
	"mode_of_transport",
	"customer",
	"supplier",
)


def execute():
	"""Condition fields got a for_ prefix so global defaults (country, item_group...) no longer fill them."""
	doctype = "Document Requirement Template"
	for old in OLD_FIELDS:
		if frappe.db.has_column(doctype, old):
			rename_field(doctype, old, f"for_{old}")
