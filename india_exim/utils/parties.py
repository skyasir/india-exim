"""Consignee, Buyer and Notify Party on export orders and invoices.

Each party is a Customer, one of its Addresses and one of its Contacts. The
address and contact are also kept as text beside the links, so a printed or
submitted document keeps what was picked even if the Address or Contact
record changes later.
"""

import re

import frappe
from frappe.contacts.doctype.address.address import get_address_display, get_default_address
from frappe.contacts.doctype.contact.contact import get_default_contact
from frappe.utils import strip_html

PARTIES = ("consignee", "buyer", "notify")


@frappe.whitelist()
def get_party_details(
	customer: str | None = None, address: str | None = None, contact: str | None = None
) -> dict:
	"""Address and contact text for a party.

	With a customer, its default address and contact are picked; with an
	address or a contact, only that one is read."""
	details = {}
	if customer:
		frappe.has_permission("Customer", "read", customer, throw=True)
		address = get_default_address("Customer", customer)
		contact = get_default_contact("Customer", customer)
		details.update(address=address or "", contact=contact or "")

	if address:
		frappe.has_permission("Address", "read", address, throw=True)
		details["address_display"] = address_text(address)
	if contact:
		frappe.has_permission("Contact", "read", contact, throw=True)
		details["contact_display"] = contact_text(contact)
	return details


def address_text(address: str) -> str:
	"""The address as plain lines: the template renders HTML with <br>."""
	html = get_address_display(address) or ""
	text = strip_html(re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE))
	return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def contact_text(contact: str) -> str:
	values = frappe.db.get_value(
		"Contact", contact, ["full_name", "mobile_no", "phone", "email_id"], as_dict=True
	)
	if not values:
		return ""
	phone = values.mobile_no or values.phone
	lines = (
		values.full_name,
		f"Tel: {phone}" if phone else "",
		f"Email: {values.email_id}" if values.email_id else "",
	)
	return "\n".join(line for line in lines if line)


def fill_party_details(doc, method=None):
	"""Keep the address and contact text in step with the links on save: filled
	when missing (a document made through the API or a data import), cleared
	when its link is cleared."""
	for party in PARTIES:
		for link, display, render in (
			(f"exim_{party}_address", f"exim_{party}_address_display", address_text),
			(f"exim_{party}_contact", f"exim_{party}_contact_display", contact_text),
		):
			if not doc.meta.has_field(display):
				continue
			value = doc.get(link)
			if not value:
				doc.set(display, "")
			elif not doc.get(display):
				doc.set(display, render(value) or "")
