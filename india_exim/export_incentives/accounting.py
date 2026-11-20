"""Journal entries for export incentives (Duty Drawback, RoDTEP)."""

import frappe
from frappe import _
from frappe.utils import flt

from india_exim.setup.accounts import get_exim_account

# scheme -> (total fieldname on Shipping Bill, receivable account field, income account field)
ACCRUAL_HEADS = {
	"Duty Drawback": ("total_drawback", "exim_drawback_receivable_account", "exim_drawback_income_account"),
	"RoDTEP": ("total_rodtep", "exim_rodtep_receivable_account", "exim_rodtep_income_account"),
}


def make_journal_entry(
	company: str,
	posting_date,
	rows: list[tuple[str, float, float]],
	remark: str,
	reference_doctype: str,
	reference_name: str,
) -> str:
	"""Create and submit a Journal Entry. rows: (account, debit, credit)."""
	cost_center = frappe.get_cached_value("Company", company, "exim_cost_center") or frappe.get_cached_value(
		"Company", company, "cost_center"
	)
	journal_entry = frappe.new_doc("Journal Entry")
	journal_entry.update(
		{
			"voucher_type": "Journal Entry",
			"company": company,
			"posting_date": posting_date,
			"user_remark": remark,
			"exim_reference_type": reference_doctype,
			"exim_reference_name": reference_name,
		}
	)
	for account, debit, credit in rows:
		if not flt(debit) and not flt(credit):
			continue
		journal_entry.append(
			"accounts",
			{
				"account": account,
				"debit_in_account_currency": flt(debit, 2),
				"credit_in_account_currency": flt(credit, 2),
				"cost_center": cost_center,
			},
		)
	journal_entry.flags.ignore_permissions = True
	journal_entry.insert()
	journal_entry.submit()
	return journal_entry.name


def make_incentive_accrual(shipping_bill) -> str | None:
	"""Book Drawback / RoDTEP receivable against incentive income on the LEO date."""
	rows = []
	for _scheme, (total_field, receivable_field, income_field) in ACCRUAL_HEADS.items():
		amount = flt(shipping_bill.get(total_field))
		if not amount:
			continue
		rows.append((get_exim_account(shipping_bill.company, receivable_field), amount, 0))
		rows.append((get_exim_account(shipping_bill.company, income_field), 0, amount))

	if not rows:
		return None

	journal_entry = make_journal_entry(
		shipping_bill.company,
		shipping_bill.leo_date,
		rows,
		_("Export incentives accrued on LEO for Shipping Bill {0} dated {1}").format(
			shipping_bill.shipping_bill_number, frappe.format(shipping_bill.shipping_bill_date, "Date")
		),
		"Shipping Bill",
		shipping_bill.name,
	)
	shipping_bill.db_set("accrual_journal_entry", journal_entry)
	return journal_entry


def cancel_accrual(shipping_bill) -> None:
	"""Cancel the LEO accrual and any later reversals posted for this shipping bill."""
	names = frappe.get_all(
		"Journal Entry",
		filters={
			"exim_reference_type": "Shipping Bill",
			"exim_reference_name": shipping_bill.name,
			"docstatus": 1,
		},
		pluck="name",
		order_by="creation desc",
	)
	for name in names:
		journal_entry = frappe.get_doc("Journal Entry", name)
		journal_entry.flags.ignore_permissions = True
		journal_entry.cancel()


def on_journal_entry_cancel(doc, method=None):
	"""Cancelling a receipt entry removes it from the claim it was recorded on."""
	if doc.get("exim_reference_type") not in ("Export Incentive Claim", "GST Refund Claim"):
		return
	claim = frappe.get_doc(doc.exim_reference_type, doc.exim_reference_name)
	remaining = [row for row in claim.receipts if row.journal_entry != doc.name]
	if len(remaining) == len(claim.receipts):
		return
	claim.receipts = remaining
	claim.flags.ignore_validate_update_after_submit = True
	claim.flags.ignore_links = True
	if claim.doctype == "Export Incentive Claim":
		claim.set_totals()
	claim.save(ignore_permissions=True)
	claim.set_status(update=True)


# scheme -> (accrued total field, reversed field) on Shipping Bill
REVERSAL_FIELDS = {
	"Duty Drawback": ("total_drawback", "drawback_reversed"),
	"RoDTEP": ("total_rodtep", "rodtep_reversed"),
}


def sync_incentive_reversal(shipping_bill, reduced_value: float) -> str | None:
	"""Take back incentives in proportion to the export value that will not be realised.

	`reduced_value` is the invoice value credited (credit notes after shipment) or written off,
	in the shipping bill currency. Drawback and RoDTEP are only due on realised exports, so the
	same share of what was accrued is reversed: Dr Export Incentive Recovery, Cr the receivable.
	The posted amounts are kept on the shipping bill, so a later change (another credit note, a
	cancelled one) posts only the difference, in either direction.
	"""
	if not shipping_bill.accrual_journal_entry or not flt(shipping_bill.total_invoice_value):
		return None
	share = min(max(flt(reduced_value) / flt(shipping_bill.total_invoice_value), 0), 1)
	company = shipping_bill.company
	recovery_account = get_exim_account(company, "exim_incentive_recovery_account")

	rows, updates = [], {}
	for scheme, (total_field, reversed_field) in REVERSAL_FIELDS.items():
		target = flt(flt(shipping_bill.get(total_field)) * share, 2)
		delta = flt(target - flt(shipping_bill.get(reversed_field)), 2)
		if abs(delta) < 0.01:
			continue
		receivable = get_exim_account(company, ACCRUAL_HEADS[scheme][1])
		if delta > 0:
			rows += [(recovery_account, delta, 0), (receivable, 0, delta)]
		else:
			rows += [(receivable, -delta, 0), (recovery_account, 0, -delta)]
		updates[reversed_field] = target

	if not rows:
		return None
	journal_entry = make_journal_entry(
		company,
		frappe.utils.today(),
		rows,
		_(
			"Export incentives adjusted for Shipping Bill {0}: {1}% of the export value credited or written off"
		).format(shipping_bill.shipping_bill_number, flt(share * 100, 2)),
		"Shipping Bill",
		shipping_bill.name,
	)
	shipping_bill.db_set(updates)
	return journal_entry
