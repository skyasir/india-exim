"""Dated lookups: law is stored as data with effective dates, never hard-coded."""

import frappe
from frappe import _
from frappe.utils import date_diff, flt, formatdate, getdate

SCHEDULE_SCHEMES = ("Duty Drawback", "RoSCTL")
STALE_RATE_DAYS = 16  # CBIC notifies customs exchange rates twice a month


def get_tariff_rate(customs_tariff_item: str, on_date) -> frappe._dict:
	"""Customs duty rates for a tariff item in force on a date."""
	rate = find_tariff_rate(customs_tariff_item, on_date)
	if rate:
		return rate

	frappe.throw(
		_("No customs duty rate is set for Tariff Item {0} on {1}.").format(
			frappe.bold(customs_tariff_item), formatdate(on_date)
		)
		+ "<br>"
		+ _("Use Add Duty Rate on the Bill of Entry, or add it on the Item's Export & Import tab."),
		title=_("Customs Duty Rate Missing"),
	)


def find_tariff_rate(customs_tariff_item: str, on_date) -> frappe._dict | None:
	on_date = getdate(on_date)
	rates = frappe.get_all(
		"Customs Tariff Rate",
		filters={
			"parent": customs_tariff_item,
			"parenttype": "Customs Tariff Item",
			"effective_from": ("<=", on_date),
		},
		fields=[
			"effective_from",
			"effective_to",
			"bcd_rate",
			"sws_rate",
			"aidc_rate",
			"other_duty_rate",
			"notification",
		],
		order_by="effective_from desc",
	)
	for rate in rates:
		if not rate.effective_to or getdate(rate.effective_to) >= on_date:
			return rate
	return None


def get_incentive_rate(
	scheme: str,
	customs_tariff_item: str,
	on_date,
	schedule_serial_no: str | None = None,
	item_code: str | None = None,
) -> frappe._dict | None:
	"""Export incentive (RoDTEP / Drawback / RoSCTL) rate in force on a date, or None. A rate for
	this item alone (brand rate) comes first; otherwise the tariff code's rate. With a schedule
	serial number, only that entry of the schedule is considered."""
	if item_code:
		own = find_incentive_rate({"scheme": scheme, "item_code": item_code}, customs_tariff_item, on_date)
		if own:
			return own
	filters = {"scheme": scheme, "item_code": ("is", "not set")}
	if schedule_serial_no:
		filters["schedule_serial_no"] = schedule_serial_no
		return find_incentive_rate(filters, customs_tariff_item, on_date) or find_incentive_rate(
			filters, None, on_date
		)
	rate = find_incentive_rate(filters, customs_tariff_item, on_date)
	if rate or scheme not in SCHEDULE_SCHEMES:
		return rate
	# the schedule goes by heading: clear only when the heading has one entry
	entries = get_schedule_entries(scheme, customs_tariff_item, on_date)
	if len(entries) != 1:
		return None
	filters["schedule_serial_no"] = entries[0].schedule_serial_no
	return find_incentive_rate(filters, None, on_date)


def get_schedule_entries(scheme: str, customs_tariff_item: str | None, on_date) -> list[frappe._dict]:
	"""Entries of the drawback or RoSCTL schedule in force for the heading of an ITC-HS code."""
	if not customs_tariff_item:
		return []
	return frappe.get_all(
		"Export Incentive Rate",
		filters={
			"scheme": scheme,
			"customs_tariff_item": ("is", "not set"),
			"schedule_serial_no": ("like", f"{customs_tariff_item[:4]}%"),
			"effective_from": ("<=", getdate(on_date)),
		},
		or_filters=[["effective_to", "is", "not set"], ["effective_to", ">=", getdate(on_date)]],
		fields=["schedule_serial_no", "description"],
		order_by="schedule_serial_no",
		limit=0,
	)


def get_rosctl_rate(
	customs_tariff_item: str, on_date, schedule_serial_no: str | None = None
) -> frappe._dict | None:
	"""RoSCTL follows the drawback serial number: the item's entry, else a rate for the whole code."""
	rate = (
		get_incentive_rate("RoSCTL", customs_tariff_item, on_date, schedule_serial_no)
		if schedule_serial_no
		else None
	)
	if rate:
		return rate
	if schedule_serial_no:
		return find_incentive_rate(
			{"scheme": "RoSCTL", "schedule_serial_no": ("is", "not set")}, customs_tariff_item, on_date
		)
	return get_incentive_rate("RoSCTL", customs_tariff_item, on_date)


def find_incentive_rate(filters: dict, customs_tariff_item: str | None, on_date) -> frappe._dict | None:
	on_date = getdate(on_date)
	filters = {
		**filters,
		"customs_tariff_item": customs_tariff_item or ("is", "not set"),
		"effective_from": ("<=", on_date),
	}
	rates = frappe.get_all(
		"Export Incentive Rate",
		filters=filters,
		fields=[
			"name",
			"rate",
			"amount_per_unit",
			"cap_per_unit",
			"cap_uom",
			"central_rate",
			"central_cap_per_unit",
			"effective_to",
			"schedule_serial_no",
			"notification",
			"data_source",
		],
		order_by="effective_from desc",
	)
	for rate in rates:
		if not rate.effective_to or getdate(rate.effective_to) >= on_date:
			return rate
	return None


def get_customs_exchange_rate(currency: str, on_date, direction: str = "Export") -> float:
	"""CBIC notified exchange rate in force on a date. direction is 'Export' or 'Import'."""
	if currency == "INR":
		return 1.0

	fieldname = "export_rate" if direction == "Export" else "import_rate"
	rate = frappe.get_all(
		"Customs Exchange Rate",
		filters={"currency": currency, "effective_from": ("<=", getdate(on_date))},
		fields=[fieldname],
		order_by="effective_from desc",
		limit=1,
	)
	if not rate:
		frappe.throw(
			_("No CBIC customs exchange rate for {0} is set on or before {1}.").format(
				frappe.bold(currency), formatdate(on_date)
			),
			title=_("Customs Exchange Rate Missing"),
		)
	return flt(rate[0][fieldname])


def warn_stale_exchange_rate(currency: str, on_date) -> None:
	"""A newer customs rate has probably been notified: the document's value would be wrong."""
	if currency == "INR":
		return
	effective_from = frappe.db.get_value(
		"Customs Exchange Rate",
		{"currency": currency, "effective_from": ("<=", getdate(on_date))},
		"effective_from",
		order_by="effective_from desc",
	)
	if effective_from and date_diff(on_date, effective_from) > STALE_RATE_DAYS:
		frappe.msgprint(
			_(
				"The latest customs exchange rate for {0} is from {1}. Enter the rate CBIC notified since, or the value and incentives will be wrong."
			).format(currency, formatdate(effective_from))
			+ f' <a href="/desk/customs-exchange-rate/new?currency={currency}">{_("Add Rate")}</a>',
			title=_("Customs Exchange Rate May Be Old"),
			indicator="orange",
		)


def get_valid_lut(company: str, on_date) -> str | None:
	"""Letter of Undertaking valid for the company on a date."""
	on_date = getdate(on_date)
	return frappe.db.get_value(
		"Letter of Undertaking",
		{"company": company, "valid_from": ("<=", on_date), "valid_upto": (">=", on_date)},
		"name",
	)


def get_schedule_serial_numbers(scheme: str, customs_tariff_item: str) -> list[str]:
	"""The schedule entries for a tariff item: its own, newest first, then its heading's."""
	own = frappe.get_all(
		"Export Incentive Rate",
		filters={
			"scheme": scheme,
			"customs_tariff_item": customs_tariff_item,
			"schedule_serial_no": ("is", "set"),
			"item_code": ("is", "not set"),
		},
		pluck="schedule_serial_no",
		order_by="effective_from desc",
	)
	entries = get_schedule_entries(scheme, customs_tariff_item, getdate())
	return list(dict.fromkeys([*own, *(entry.schedule_serial_no for entry in entries)]))
