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
	if not shipping_bill.accrual_journal_entry:
		return
	journal_entry = frappe.get_doc("Journal Entry", shipping_bill.accrual_journal_entry)
	if journal_entry.docstatus == 1:
		journal_entry.flags.ignore_permissions = True
		journal_entry.cancel()
