"""Advance Authorisation and EPCG: imports debited and exports credited against a licence.

The licence (Export Authorisation) holds what DGFT allowed and required. What was used is read
from the submitted Bills of Entry and Shipping Bills that name it, the same way realisation is
read from payments: users only pick the licence on the customs documents, and the position here
is rebuilt from them whenever one is submitted or cancelled.
"""

import frappe
from frappe import _
from frappe.utils import add_months, flt, getdate, today

DEFAULT_PERIODS = {
	# scheme: (import validity months, export obligation months)
	"Advance Authorisation": (12, 18),
	"EPCG": (24, 72),
}
EPCG_BLOCK_1_MONTHS = 48


def match_row(rows, item_code: str | None, tariff: str | None):
	"""The licence row for an item: its own item first, then a row for the whole ITC-HS code."""
	for row in rows:
		if row.item_code and row.item_code == item_code:
			return row
	for row in rows:
		if not row.item_code and row.customs_tariff_item == tariff:
			return row
	return None


def refresh_authorisation(name: str) -> None:
	"""Rebuild the licence position after a Bill of Entry or Shipping Bill naming it changes."""
	if not name:
		return
	doc = frappe.get_doc("Export Authorisation", name)
	compute_position(doc)
	doc.set_status()
	for row in doc.imports + doc.exports:
		row.db_update()
	doc.db_update()
	doc.notify_update()


def compute_position(doc) -> None:
	"""Imports, duty saved and exports from the submitted customs documents naming the licence."""
	for row in doc.imports:
		row.qty_imported = row.cif_imported = row.duty_saved = 0
	for row in doc.exports:
		row.qty_exported = row.fob_exported = 0

	unmatched_duty = unmatched_cif = 0.0
	for item in get_imports(doc.name) if not doc.is_new() else []:
		row = match_row(doc.imports, item.item_code, item.exim_customs_tariff_item)
		duty = flt(item.exim_duty_foregone) + flt(item.exim_igst_foregone)
		if row:
			row.qty_imported += flt(item.qty)
			row.cif_imported += flt(item.assessable_value)
			row.duty_saved += duty
		else:
			unmatched_cif += flt(item.assessable_value)
			unmatched_duty += duty

	unmatched_fob = 0.0
	for item in get_exports(doc.name) if not doc.is_new() else []:
		row = match_row(doc.exports, item.item_code, item.customs_tariff_item)
		if row:
			row.qty_exported += flt(item.uqc_qty or item.qty)
			row.fob_exported += flt(item.fob_value_inr)
		else:
			unmatched_fob += flt(item.fob_value_inr)

	doc.set_totals(extra_cif=unmatched_cif, extra_duty=unmatched_duty, extra_fob=unmatched_fob)


def get_imports(name: str) -> list:
	boe = frappe.qb.DocType("Bill of Entry")
	item = frappe.qb.DocType("Bill of Entry Item")
	return (
		frappe.qb.from_(item)
		.join(boe)
		.on(boe.name == item.parent)
		.select(
			item.item_code,
			item.exim_customs_tariff_item,
			item.qty,
			item.assessable_value,
			item.exim_duty_foregone,
			item.exim_igst_foregone,
		)
		.where(boe.docstatus == 1)
		.where(item.exim_authorisation == name)
	).run(as_dict=True)


def get_exports(name: str) -> list:
	sb = frappe.qb.DocType("Shipping Bill")
	item = frappe.qb.DocType("Shipping Bill Item")
	return (
		frappe.qb.from_(item)
		.join(sb)
		.on(sb.name == item.parent)
		.select(item.item_code, item.customs_tariff_item, item.qty, item.uqc_qty, item.fob_value_inr)
		.where(sb.docstatus == 1)
		.where(sb.export_authorisation == name)
	).run(as_dict=True)


def get_active_authorisation(name: str, company: str, on_date, purpose: str) -> frappe._dict:
	"""The licence, checked for use on a customs document of this company and date."""
	details = frappe.db.get_value(
		"Export Authorisation",
		name,
		[
			"company",
			"scheme",
			"status",
			"import_validity_upto",
			"eo_period_upto",
			"authorisation_date",
			"drawback_admissible",
			"rodtep_admissible",
		],
		as_dict=True,
	)
	if not details:
		frappe.throw(_("Export Authorisation {0} does not exist.").format(name))
	if details.company != company:
		frappe.throw(_("Export Authorisation {0} belongs to {1}.").format(name, details.company))
	if details.status in ("Cancelled", "Redeemed", "Regularised"):
		frappe.throw(_("Export Authorisation {0} is {1}.").format(name, _(details.status)))
	on_date = getdate(on_date)
	if details.authorisation_date and on_date < getdate(details.authorisation_date):
		frappe.throw(_("{0} is dated before Export Authorisation {1} was issued.").format(purpose, name))
	if (
		purpose == _("Bill of Entry")
		and details.import_validity_upto
		and on_date > getdate(details.import_validity_upto)
	):
		frappe.throw(
			_("Imports under Export Authorisation {0} were allowed until {1}.").format(
				name, frappe.format(details.import_validity_upto, {"fieldtype": "Date"})
			)
		)
	return details


def validate_bill_of_entry(doc, method=None):
	"""Bill of Entry under a licence: licence valid, items allowed, quantities within balance."""
	validate_row_quantities(doc)
	for name in dict.fromkeys(row.exim_authorisation for row in doc.items if row.get("exim_authorisation")):
		validate_licence(doc, name)


def validate_row_quantities(doc) -> None:
	"""A line split over licences: the parts together cannot exceed what is pending on the invoice."""
	parts = {}
	for row in doc.items:
		if row.get("pi_detail"):
			parts.setdefault(row.pi_detail, []).append(row)
	for detail, rows in parts.items():
		if len(rows) < 2 or doc.docstatus == 2:
			continue
		pending = frappe.db.get_value("Purchase Invoice Item", detail, "pending_boe_qty")
		total = sum(flt(row.qty) for row in rows)
		if total - flt(pending) > 0.0001:
			frappe.throw(
				_("Rows {0}: {1} of {2} together, but only {3} is pending on the purchase invoice.").format(
					", ".join(str(row.idx) for row in rows), total, rows[0].item_code, flt(pending)
				)
			)


def validate_licence(doc, name: str) -> None:
	get_active_authorisation(name, doc.company, doc.bill_of_entry_date or today(), _("Bill of Entry"))
	licence = frappe.get_doc("Export Authorisation", name)
	used, used_cif = {}, {}  # submitted bills, then the rows of this one as they are checked
	for item in get_imports(name):
		row = match_row(licence.imports, item.item_code, item.exim_customs_tariff_item)
		if row:
			used[row.name] = used.get(row.name, 0) + flt(item.qty)
			used_cif[row.name] = used_cif.get(row.name, 0) + flt(item.assessable_value)
	over_value = {}
	for item in [row for row in doc.items if row.get("exim_authorisation") == name]:
		row = match_row(licence.imports, item.item_code, item.get("exim_customs_tariff_item"))
		if not row:
			frappe.throw(
				_("Row {0}: {1} (ITC-HS {2}) is not among the imports allowed under {3}.").format(
					item.idx, item.item_code, item.get("exim_customs_tariff_item") or "-", name
				)
			)
		if flt(row.qty_allowed):
			already = used.get(row.name, 0)
			if already + flt(item.qty) > flt(row.qty_allowed) + 0.0001:
				frappe.throw(
					_("Row {0}: only {1} {2} of {3} is left under {4}.").format(
						item.idx, flt(row.qty_allowed) - already, row.uom or "", row.customs_tariff_item, name
					)
				)
		used[row.name] = used.get(row.name, 0) + flt(item.qty)
		used_cif[row.name] = used_cif.get(row.name, 0) + flt(item.assessable_value)
		if flt(row.cif_allowed) and used_cif[row.name] - flt(row.cif_allowed) > 0.5:
			over_value[row.name] = row
	if over_value and doc.docstatus < 2:
		# a warning, not an error: the bill records what Customs accepted, and the rupee value of
		# the same licence moves with the exchange rate
		frappe.msgprint(
			"<br>".join(
				_("CIF value of {0} would reach {1} against {2} allowed under {3}.").format(
					row.customs_tariff_item,
					frappe.format(used_cif[row.name], "Currency"),
					frappe.format(row.cif_allowed, "Currency"),
					name,
				)
				for row in over_value.values()
			)
			+ "<br>"
			+ _("Check the licence, and have its value enhanced before filing if needed."),
			title=_("Licence Value Exceeded"),
			indicator="orange",
		)


def set_duty_foregone(bill_of_entry) -> None:
	"""Imports under a licence pay no basic customs duty: what would have been paid is recorded as
	duty foregone and the payable duty is zero. Called after the duty is worked out."""
	for item in bill_of_entry.items:
		if item.get("exim_authorisation"):
			item.exim_duty_foregone = flt(item.customs_duty)
			item.customs_duty = 0
		else:
			item.exim_duty_foregone = 0


def set_igst_foregone(bill_of_entry) -> None:
	"""IGST not charged on an authorised import counts as saved (EPCG obligation is a multiple of
	duties and taxes saved). Worked out at the rate the bill would have charged; zero when IGST
	was charged."""
	total = 0.0
	for item in bill_of_entry.items:
		item.exim_igst_foregone = 0
		if item.get("exim_authorisation") and not flt(item.get("igst_amount")):
			rate = (bill_of_entry.flags.exempt_tax_rates or {}).get(item.name) or get_gst_rate(item.item_code)
			item.exim_igst_foregone = flt(
				(flt(item.assessable_value) + flt(item.exim_duty_foregone)) * rate / 100, 2
			)
		total += flt(item.exim_duty_foregone) + flt(item.exim_igst_foregone)
	bill_of_entry.exim_total_duty_foregone = total


def exempt_taxes(bill_of_entry) -> None:
	"""IGST and compensation cess are exempt too on imports under a licence: the tax rows stay (India
	Compliance needs the IGST row) with a zero rate for the items under a licence. Called once India Compliance
	has set the item-wise rates and before it works out the amounts."""
	bill_of_entry.flags.exempt_tax_rates = {}
	exempt = {item.name for item in bill_of_entry.items if item.get("exim_authorisation")}
	if not exempt or not bill_of_entry.get("exim_igst_exempt"):
		return
	for tax in bill_of_entry.taxes:
		if tax.charge_type == "Actual":
			continue  # entered by the user
		rates = frappe.parse_json(tax.item_wise_tax_rates or "{}")
		if tax.charge_type == "On Net Total":
			for name, rate in rates.items():
				saved = bill_of_entry.flags.exempt_tax_rates
				if name in exempt:
					saved[name] = saved.get(name, 0) + flt(rate)
		tax.item_wise_tax_rates = frappe.as_json(
			{name: 0 if name in exempt else rate for name, rate in rates.items()}, indent=None
		)


def get_gst_rate(item_code: str | None) -> float:
	if not item_code:
		return 0.0
	templates = frappe.get_all(
		"Item Tax", filters={"parent": item_code, "parenttype": "Item"}, pluck="item_tax_template"
	)
	for template in templates:
		rate = frappe.db.get_value("Item Tax Template", template, "gst_rate")
		if flt(rate):
			return flt(rate)
	return 0.0


def apply_to_shipping_bill(shipping_bill) -> None:
	"""Shipping Bill under a licence: licence valid, incentives only where the licence allows."""
	name = shipping_bill.get("export_authorisation")
	if not name:
		return
	details = get_active_authorisation(
		name, shipping_bill.company, shipping_bill.shipping_bill_date or today(), _("Shipping Bill")
	)
	for row in shipping_bill.items:
		if not details.drawback_admissible:
			row.claim_drawback = 0
		if not details.rodtep_admissible:
			row.claim_rodtep = 0
			row.claim_rosctl = 0


def licences_of(doc) -> set:
	if doc.doctype == "Bill of Entry":
		return {row.get("exim_authorisation") for row in doc.items}
	return {doc.get("export_authorisation")}


def set_row_authorisations(bill_of_entry) -> None:
	"""The licence is kept on each row, as Customs debits it. One picked on the header fills every row
	that has none of its own, and changing it there changes those rows."""
	before = bill_of_entry.get_doc_before_save()
	old = before.get("exim_authorisation") if before else None
	new = bill_of_entry.get("exim_authorisation")
	for row in bill_of_entry.items:
		if old != new and row.get("exim_authorisation") == old:
			row.exim_authorisation = None
		if new and not row.get("exim_authorisation"):
			row.exim_authorisation = new


def on_customs_document_change(doc, method=None):
	"""doc_event / controller hook for Bill of Entry and Shipping Bill submit and cancel."""
	names = licences_of(doc)
	before = doc.get_doc_before_save() if hasattr(doc, "get_doc_before_save") else None
	if before:
		names |= licences_of(before)
	for name in [name for name in names if name]:
		refresh_authorisation(name)


def refresh_statuses() -> None:
	"""Daily: the EO period passing changes the status without any document being saved."""
	for name in frappe.get_all(
		"Export Authorisation", filters={"status": ("in", ("Active", "EO Fulfilled"))}, pluck="name"
	):
		doc = frappe.get_doc("Export Authorisation", name)
		before = doc.status
		doc.set_status()
		if doc.status != before:
			doc.db_set("status", doc.status)


def default_dates(doc) -> None:
	import_months, eo_months = DEFAULT_PERIODS[doc.scheme]
	if not doc.import_validity_upto:
		doc.import_validity_upto = add_months(doc.authorisation_date, import_months)
	if not doc.eo_period_upto:
		doc.eo_period_upto = add_months(doc.authorisation_date, eo_months)
	if doc.scheme == "EPCG" and not doc.block_1_upto:
		doc.block_1_upto = add_months(doc.authorisation_date, EPCG_BLOCK_1_MONTHS)
