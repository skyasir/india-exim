# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import formatdate, getdate


class TradeAgreement(Document):
	def validate(self):
		if any(row.country == "India" for row in self.partner_countries):
			frappe.throw(_("List only the partner countries; India is a party to every agreement here."))
		if "RVC" in (self.origin_criterion or "") and not self.rvc_percent:
			frappe.throw(
				_("Set the Minimum RVC % for the origin criterion {0}.").format(self.origin_criterion)
			)


def get_partner_countries(agreement: str) -> set[str]:
	return set(
		frappe.get_all(
			"Country Group Member",
			filters={"parenttype": "Trade Agreement", "parent": agreement},
			pluck="country",
		)
	)


def validate_claim(agreement: str, country: str | None, on_date, label: str) -> frappe._dict:
	"""The agreement, if it can be used for goods of (or going to) this country on this date."""
	doc = frappe.get_cached_doc("Trade Agreement", agreement)
	if doc.disabled:
		frappe.throw(_("Trade Agreement {0} is disabled.").format(frappe.bold(agreement)))
	if not country:
		frappe.throw(_("Set the {0} to claim {1}.").format(label, frappe.bold(agreement)))
	if country not in get_partner_countries(agreement):
		frappe.throw(
			_("{0} is not a partner country of {1}.").format(frappe.bold(country), frappe.bold(agreement))
		)
	if doc.in_force_from and on_date and getdate(on_date) < getdate(doc.in_force_from):
		frappe.throw(
			_("{0} is in force only from {1}.").format(frappe.bold(agreement), formatdate(doc.in_force_from))
		)
	return doc


SEEDED_NOTE = (
	"Loaded by India EXIM as a starting point. Check the notifications and the agreement's"
	" product-specific rules before relying on it."
)


def seed_trade_agreements():
	"""India's agreements in force, as a starting point. Records already there are kept as they are."""
	from india_exim.setup.seed import load

	known_countries = set(frappe.get_all("Country", pluck="name"))
	for row in load("trade_agreements.json"):
		if frappe.db.exists("Trade Agreement", row["agreement_name"]):
			continue
		countries = [{"country": country} for country in row.pop("countries") if country in known_countries]
		row["verify_note"] = " ".join(part for part in (row.get("verify_note"), SEEDED_NOTE) if part)
		frappe.get_doc({"doctype": "Trade Agreement", **row, "partner_countries": countries}).insert(
			ignore_permissions=True
		)
