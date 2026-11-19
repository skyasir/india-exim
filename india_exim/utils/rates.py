"""Dated lookups: law is stored as data with effective dates, never hard-coded."""

import frappe
from frappe import _
from frappe.utils import flt, formatdate, getdate


def get_tariff_rate(customs_tariff_item: str, on_date) -> frappe._dict:
	"""Customs duty rates for a tariff item in force on a date."""
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

	frappe.throw(
		_("No customs duty rate is set for Tariff Item {0} on {1}.").format(
			frappe.bold(customs_tariff_item), formatdate(on_date)
		),
		title=_("Customs Duty Rate Missing"),
	)


def get_incentive_rate(scheme: str, customs_tariff_item: str, on_date) -> frappe._dict | None:
	"""Export incentive (RoDTEP / Drawback / RoSCTL) rate in force on a date, or None."""
	on_date = getdate(on_date)
	rates = frappe.get_all(
		"Export Incentive Rate",
		filters={
			"scheme": scheme,
			"customs_tariff_item": customs_tariff_item,
			"effective_from": ("<=", on_date),
		},
		fields=[
			"name",
			"rate",
			"cap_per_unit",
			"cap_uom",
			"effective_to",
			"schedule_serial_no",
			"notification",
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


def get_valid_lut(company: str, on_date) -> str | None:
	"""Letter of Undertaking valid for the company on a date."""
	on_date = getdate(on_date)
	return frappe.db.get_value(
		"Letter of Undertaking",
		{"company": company, "valid_from": ("<=", on_date), "valid_upto": (">=", on_date)},
		"name",
	)
