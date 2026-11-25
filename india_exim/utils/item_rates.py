"""Incentive and import duty rates on the Item: shown and entered there, kept on the tariff code."""

import frappe
from frappe import _
from frappe.utils import add_days, cint, flt, getdate, today

from india_exim.utils.rates import SCHEDULE_SCHEMES, get_schedule_entries

SCHEMES = ("RoDTEP", "Duty Drawback", "RoSCTL")


@frappe.whitelist()
def get_incentive_rates(
	customs_tariff_item: str, item_code: str | None = None, drawback_serial_no: str | None = None
) -> list[dict]:
	"""Rates in force today or later for the tariff code, brand rates of this item, and the drawback
	and RoSCTL entries of the item's schedule serial number."""
	frappe.has_permission("Export Incentive Rate", "read", throw=True)
	serials = [drawback_serial_no] if drawback_serial_no else []
	if not serials:
		for scheme in SCHEDULE_SCHEMES:
			entries = get_schedule_entries(scheme, customs_tariff_item, today())
			serials += [entries[0].schedule_serial_no] if len(entries) == 1 else []
	rates = []
	for filters in (
		{"customs_tariff_item": customs_tariff_item},
		{"customs_tariff_item": ("is", "not set"), "schedule_serial_no": ("in", serials or [""])},
	):
		rates += get_current_rates(filters)
	from india_exim.overrides.item import get_notified_text

	rows = [rate for rate in rates if not rate.item_code or rate.item_code == item_code]
	for row in rows:
		row.notified = None
		if getdate(row.effective_from) <= getdate():
			row.notified = get_notified_text(row.scheme, customs_tariff_item, row)
	return rows


def get_current_rates(filters: dict) -> list[dict]:
	return frappe.get_list(
		"Export Incentive Rate",
		filters=filters,
		or_filters=[["effective_to", "is", "not set"], ["effective_to", ">=", today()]],
		fields=[
			"name",
			"scheme",
			"schedule_serial_no",
			"item_code",
			"rate",
			"amount_per_unit",
			"cap_per_unit",
			"cap_uom",
			"central_rate",
			"central_cap_per_unit",
			"effective_from",
			"effective_to",
			"notification",
			"data_source",
		],
		order_by="scheme desc, effective_from asc",
		limit=0,
	)


@frappe.whitelist()
def get_duty_rates(customs_tariff_item: str) -> list[dict]:
	frappe.has_permission("Customs Tariff Item", "read", customs_tariff_item, throw=True)
	return frappe.get_all(
		"Customs Tariff Rate",
		filters={"parent": customs_tariff_item, "parenttype": "Customs Tariff Item"},
		or_filters=[["effective_to", "is", "not set"], ["effective_to", ">=", today()]],
		fields=[
			"name",
			"bcd_rate",
			"sws_rate",
			"aidc_rate",
			"other_duty_rate",
			"effective_from",
			"effective_to",
			"notification",
		],
		order_by="effective_from asc",
		limit=0,
	)


@frappe.whitelist()
def count_other_items(customs_tariff_item: str, item_code: str | None = None) -> int:
	"""Other items a rate of this tariff code also applies to."""
	frappe.has_permission("Item", "read", throw=True)
	return frappe.db.count(
		"Item", {"exim_customs_tariff_item": customs_tariff_item, "name": ("!=", item_code or "")}
	)


@frappe.whitelist(methods=["POST"])
def add_incentive_rate(customs_tariff_item: str, values: dict | str) -> str:
	values = frappe._dict(frappe.parse_json(values))
	if values.scheme not in SCHEMES:
		frappe.throw(_("Select a scheme."))
	doc = frappe.new_doc("Export Incentive Rate")
	doc.update(
		{
			"scheme": values.scheme,
			"customs_tariff_item": customs_tariff_item,
			"schedule_serial_no": values.schedule_serial_no if values.scheme != "RoDTEP" else None,
			"item_code": values.item_code if cint(values.only_this_item) else None,
			"rate": flt(values.rate),
			"amount_per_unit": flt(values.amount_per_unit),
			"cap_per_unit": flt(values.cap_per_unit),
			"cap_uom": values.cap_uom,
			"central_rate": flt(values.central_rate),
			"central_cap_per_unit": flt(values.central_cap_per_unit),
			"effective_from": values.effective_from,
			"notification": values.notification,
		}
	)
	doc.insert()
	return doc.name


@frappe.whitelist(methods=["POST"])
def add_duty_rate(customs_tariff_item: str, values: dict | str) -> None:
	"""A new duty rate; the open-ended one before it ends the day before."""
	values = frappe._dict(frappe.parse_json(values))
	tariff = frappe.get_doc("Customs Tariff Item", customs_tariff_item)
	tariff.check_permission("write")
	start = getdate(values.effective_from)
	for row in tariff.rates:
		if not row.effective_to and getdate(row.effective_from) < start:
			row.effective_to = add_days(start, -1)
	tariff.append(
		"rates",
		{
			"effective_from": start,
			"bcd_rate": flt(values.bcd_rate),
			"sws_rate": flt(values.sws_rate),
			"aidc_rate": flt(values.aidc_rate),
			"other_duty_rate": flt(values.other_duty_rate),
			"notification": values.notification,
		},
	)
	tariff.save()
