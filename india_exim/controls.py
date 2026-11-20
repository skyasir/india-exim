"""Pre-shipment controls on export quotations, sales orders and sales invoices.

Before goods are produced or shipped, check:
- the destination country (Country > Export Controls: sanctioned, restricted, payment risk)
- the goods (Customs Tariff Item: ITC-HS export policy Prohibited / Restricted / STE, SCOMET)
- the buyer (denied-party screening recorded on the Customer, ECGC buyer limit)

Serious findings (sanctioned destination, prohibited goods, buyer not screened or a match) stop
submission when India EXIM Settings > Pre-shipment Checks is "Block" and are shown as a warning
when it is "Warn". The other findings are always warnings.
"""

import frappe
from frappe import _
from frappe.utils import add_months, flt, getdate, today


def validate(doc, method=None):
	if not doc.get("exim_is_export") or doc.docstatus != 0:
		return
	mode = frappe.db.get_single_value("India EXIM Settings", "pre_shipment_checks") or "Warn"
	if mode == "Off":
		return

	serious, notes = [], []
	check_destination(doc, serious, notes)
	check_goods(doc, serious, notes)
	check_buyer(doc, serious, notes)

	if serious and mode == "Block" and doc.get("_action") == "submit":
		frappe.throw(format_findings(serious + notes), title=_("Pre-shipment Checks"))
	if serious or notes:
		frappe.msgprint(
			format_findings(serious + notes),
			title=_("Pre-shipment Checks"),
			indicator="red" if serious else "orange",
		)


def get_customer(doc) -> str | None:
	if doc.doctype == "Quotation":
		return doc.party_name if doc.quotation_to == "Customer" else None
	return doc.get("customer")


def get_destination(doc) -> str | None:
	if doc.get("exim_destination_country"):
		return doc.exim_destination_country
	address = doc.get("shipping_address_name") or doc.get("customer_address")
	return frappe.db.get_value("Address", address, "country") if address else None


def check_destination(doc, serious: list, notes: list) -> None:
	country = get_destination(doc)
	if not country:
		return
	risk, note = frappe.db.get_value("Country", country, ["exim_trade_risk", "exim_trade_risk_note"]) or (
		None,
		None,
	)
	if not risk:
		return
	message = _("Destination {0} is marked {1}.").format(frappe.bold(country), frappe.bold(_(risk)))
	if note:
		message += " " + note
	(serious if risk == "Sanctioned" else notes).append(message)


def check_goods(doc, serious: list, notes: list) -> None:
	items = {row.item_code for row in doc.get("items") or [] if row.item_code}
	if not items:
		return
	tariffs = dict(
		frappe.get_all(
			"Item",
			filters={"name": ("in", list(items)), "exim_customs_tariff_item": ("is", "set")},
			fields=["name", "exim_customs_tariff_item"],
			as_list=True,
		)
	)
	if not tariffs:
		return
	policies = {
		row.name: row
		for row in frappe.get_all(
			"Customs Tariff Item",
			filters={"name": ("in", list(set(tariffs.values())))},
			fields=["name", "export_policy", "is_scomet", "policy_notes"],
		)
	}
	for item, tariff in sorted(tariffs.items()):
		policy = policies.get(tariff)
		if not policy:
			continue
		label = f"{frappe.bold(item)} (ITC-HS {tariff})"
		if policy.export_policy == "Prohibited":
			serious.append(_("Export of {0} is prohibited.").format(label))
		elif policy.export_policy in ("Restricted", "STE"):
			notes.append(
				_(
					"Export of {0} is {1}: an export authorisation from DGFT (or export through the State Trading Enterprise) is needed."
				).format(label, _(policy.export_policy))
			)
		if policy.is_scomet:
			notes.append(_("{0} is a SCOMET item: a SCOMET authorisation is needed.").format(label))


def check_buyer(doc, serious: list, notes: list) -> None:
	customer = get_customer(doc)
	if not customer:
		return
	details = frappe.db.get_value(
		"Customer",
		customer,
		["exim_screened_on", "exim_screening_result", "exim_ecgc_buyer_limit", "exim_ecgc_limit_valid_upto"],
		as_dict=True,
	)
	if not details:
		return
	if details.exim_screening_result == "Match - Do Not Trade":
		serious.append(_("Buyer {0} matched a denied-party list.").format(frappe.bold(customer)))
	months = frappe.db.get_single_value("India EXIM Settings", "buyer_screening_months")
	if months is None:
		months = 12
	if months and details.exim_screening_result != "Match - Do Not Trade":
		if not details.exim_screened_on:
			serious.append(
				_("Buyer {0} has not been screened against denied-party lists.").format(frappe.bold(customer))
			)
		elif getdate(add_months(details.exim_screened_on, months)) < getdate(today()):
			serious.append(
				_("Buyer {0} was last screened on {1}; screen again.").format(
					frappe.bold(customer), frappe.format(details.exim_screened_on, {"fieldtype": "Date"})
				)
			)
	check_ecgc_limit(doc, customer, details, notes)


def check_ecgc_limit(doc, customer: str, details, notes: list) -> None:
	limit = flt(details.exim_ecgc_buyer_limit)
	if not limit:
		return
	if details.exim_ecgc_limit_valid_upto and getdate(details.exim_ecgc_limit_valid_upto) < getdate(today()):
		notes.append(_("The ECGC buyer limit for {0} has expired.").format(frappe.bold(customer)))
		return
	totals = frappe.get_all(
		"GL Entry",
		filters={"party_type": "Customer", "party": customer, "company": doc.company, "is_cancelled": 0},
		fields=[{"SUM": "debit", "as": "debit"}, {"SUM": "credit", "as": "credit"}],
	)[0]
	owed = flt(totals.debit) - flt(totals.credit)
	exposure = owed + (flt(doc.base_grand_total) if doc.doctype != "Sales Invoice" else 0)
	if exposure > limit:
		notes.append(
			_("Amount owed by {0} would be {1}, above the ECGC buyer limit of {2}.").format(
				frappe.bold(customer),
				frappe.format(exposure, {"fieldtype": "Currency"}),
				frappe.format(limit, {"fieldtype": "Currency"}),
			)
		)


def format_findings(findings: list[str]) -> str:
	return "<ul>" + "".join(f"<li>{finding}</li>" for finding in findings) + "</ul>"
