import frappe


def validate(doc, method=None):
	"""Tick Is Export from the customer when the quotation is for an export customer. A quotation
	to a Lead is left as the user set it."""
	if doc.exim_is_export or doc.quotation_to != "Customer" or not doc.party_name:
		return
	if doc.is_new() and frappe.db.get_value("Customer", doc.party_name, "exim_is_export"):
		doc.exim_is_export = 1
