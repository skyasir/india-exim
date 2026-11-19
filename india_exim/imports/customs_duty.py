"""Customs duty on India Compliance's Bill of Entry: assessable value and BCD / SWS / AIDC per item.

The result is written into India Compliance's own `assessable_value` and `customs_duty` fields,
so its IGST, ITC and GL logic keeps working unchanged.
"""

import frappe
from frappe.utils import flt

from india_exim.utils.rates import get_customs_exchange_rate, get_tariff_rate

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
	items = [item for item in bill_of_entry.items if item.get("exim_customs_tariff_item")]
	for item in items:
		if not flt(item.get("exim_value_fc")):
			item.exim_value_fc = get_invoice_value(item)

	total_value = sum(flt(item.exim_value_fc) for item in items)
	for item in items:
		share = flt(item.exim_value_fc) / total_value if total_value else 0
		item.assessable_value = flt(
			flt(item.exim_value_fc) * bill_of_entry.exim_customs_exchange_rate
			+ flt(bill_of_entry.exim_additional_value) * share,
			2,
		)
		set_item_duty(item, bill_of_entry.bill_of_entry_date)


def set_item_duty(item, on_date) -> None:
	if not item.get("exim_manual_rates"):
		rate = get_tariff_rate(item.exim_customs_tariff_item, on_date)
		for field in RATE_FIELDS:
			item.set(f"exim_{field}", flt(rate.get(field)))

	assessable = flt(item.assessable_value)
	item.exim_bcd_amount = flt(assessable * flt(item.exim_bcd_rate) / 100, 2)
	item.exim_sws_amount = flt(item.exim_bcd_amount * flt(item.exim_sws_rate) / 100, 2)
	item.exim_aidc_amount = flt(assessable * flt(item.exim_aidc_rate) / 100, 2)
	item.exim_other_duty_amount = flt(assessable * flt(item.exim_other_duty_rate) / 100, 2)
	item.customs_duty = (
		item.exim_bcd_amount + item.exim_sws_amount + item.exim_aidc_amount + item.exim_other_duty_amount
	)


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
