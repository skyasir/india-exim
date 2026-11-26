"""Customs duty on India Compliance's Bill of Entry: assessable value and BCD / SWS / AIDC per item.

The result is written into India Compliance's own `assessable_value` and `customs_duty` fields,
so its IGST, ITC and GL logic keeps working unchanged.
"""

import frappe
from frappe import _
from frappe.utils import flt

from india_exim.utils.rates import (
	find_tariff_rate,
	get_customs_exchange_rate,
	get_tariff_rate,
	warn_stale_exchange_rate,
)

RATE_FIELDS = ("bcd_rate", "sws_rate", "aidc_rate", "other_duty_rate")


def set_customs_duties(bill_of_entry) -> None:
	if not bill_of_entry.get("exim_calculate_duty") or not bill_of_entry.bill_of_entry_date:
		return

	currency = get_invoice_currency(bill_of_entry)
	if not currency:
		return

	bill_of_entry.exim_currency = currency
	bill_of_entry.exim_customs_exchange_rate = get_customs_exchange_rate(
		currency, bill_of_entry.bill_of_entry_date, "Import"
	)
	warn_stale_exchange_rate(currency, bill_of_entry.bill_of_entry_date)
	items = [item for item in bill_of_entry.items if item.get("exim_customs_tariff_item")]
	for item in items:
		if not flt(item.get("exim_value_fc")):
			item.exim_value_fc = get_invoice_value(item)

	total_value = sum(flt(item.exim_value_fc) for item in items)
	agreement = bill_of_entry.get("exim_trade_agreement")
	for item in items:
		share = flt(item.exim_value_fc) / total_value if total_value else 0
		item.assessable_value = flt(
			flt(item.exim_value_fc) * bill_of_entry.exim_customs_exchange_rate
			+ flt(bill_of_entry.exim_additional_value) * share,
			2,
		)
		set_item_duty(item, bill_of_entry.bill_of_entry_date, agreement)
	bill_of_entry.exim_fta_duty_saved = sum(flt(item.get("exim_fta_duty_saved")) for item in items)

	from india_exim.dgft_licences.authorisation import set_duty_foregone

	set_duty_foregone(bill_of_entry)


def set_item_duty(item, on_date, trade_agreement: str | None = None) -> None:
	"""Duty at the tariff rate in force; under a trade agreement, at its concessional rate when the
	tariff item has one (the standard rate otherwise), with the duty saved against the standard rate."""
	standard = find_tariff_rate(item.exim_customs_tariff_item, on_date) if trade_agreement else None
	if not item.get("exim_manual_rates"):
		rate = trade_agreement and find_tariff_rate(item.exim_customs_tariff_item, on_date, trade_agreement)
		if trade_agreement and not rate:
			frappe.msgprint(
				_("Tariff Item {0} has no concessional rate under {1}; the standard rate is used.").format(
					frappe.bold(item.exim_customs_tariff_item), frappe.bold(trade_agreement)
				),
				indicator="orange",
				alert=True,
			)
		rate = rate or get_tariff_rate(item.exim_customs_tariff_item, on_date)
		for field in RATE_FIELDS:
			item.set(f"exim_{field}", flt(rate.get(field)))

	assessable = flt(item.assessable_value)
	item.exim_bcd_amount, item.exim_sws_amount, item.exim_aidc_amount, item.exim_other_duty_amount = (
		get_duty_amounts(assessable, {field: item.get(f"exim_{field}") for field in RATE_FIELDS})
	)
	item.customs_duty = (
		item.exim_bcd_amount + item.exim_sws_amount + item.exim_aidc_amount + item.exim_other_duty_amount
	)
	item.exim_fta_duty_saved = (
		max(flt(sum(get_duty_amounts(assessable, standard)) - item.customs_duty, 2), 0) if standard else 0
	)


def get_duty_amounts(assessable: float, rates) -> tuple[float, float, float, float]:
	"""BCD, SWS (on BCD), AIDC and other duty."""
	bcd = flt(assessable * flt(rates.get("bcd_rate")) / 100, 2)
	sws = flt(bcd * flt(rates.get("sws_rate")) / 100, 2)
	aidc = flt(assessable * flt(rates.get("aidc_rate")) / 100, 2)
	other = flt(assessable * flt(rates.get("other_duty_rate")) / 100, 2)
	return bcd, sws, aidc, other


def get_invoice_currency(bill_of_entry) -> str | None:
	invoices = {item.purchase_invoice for item in bill_of_entry.items if item.get("purchase_invoice")}
	currencies = {frappe.db.get_value("Purchase Invoice", invoice, "currency") for invoice in invoices}
	if len(currencies) > 1:
		frappe.throw(frappe._("All Purchase Invoices on one Bill of Entry must be in the same currency."))
	return currencies.pop() if currencies else None


def get_invoice_value(item) -> float:
	"""Invoice value (invoice currency) of the quantity on this Bill of Entry row."""
	if not item.get("pi_detail"):
		return 0.0
	net_amount, qty = frappe.db.get_value("Purchase Invoice Item", item.pi_detail, ["net_amount", "qty"])
	return flt(flt(net_amount) * flt(item.qty) / flt(qty), 2) if flt(qty) else 0.0
