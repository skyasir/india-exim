"""Export realisation and import payment status, derived from ERPNext's Payment Ledger.

Users only make ordinary Payment Entries, Journal Entries, credit notes or reconciliations against
their invoices. Each Shipping Bill / Bill of Entry reads what was settled against the invoices it
covers, so there is one owner for payment data and nothing to keep in sync by hand.
"""

import frappe
from frappe.utils import add_months, flt, getdate

TOLERANCE = 0.01


def get_invoice_settlement(invoice_doctype: str, invoice: str) -> frappe._dict:
	"""Paid and credit-noted amounts against an invoice, in the invoice currency."""
	entries = frappe.get_all(
		"Payment Ledger Entry",
		filters={"against_voucher_type": invoice_doctype, "against_voucher_no": invoice, "delinked": 0},
		fields=["voucher_type", "voucher_no", "amount_in_account_currency", "account_currency"],
	)
	details = frappe.db.get_value(
		invoice_doctype, invoice, ["currency", "conversion_rate", "company", "grand_total"], as_dict=True
	)
	own_amount = sum(row.amount_in_account_currency for row in entries if row.voucher_no == invoice)
	sign = 1 if own_amount >= 0 else -1

	paid = 0.0
	for row in entries:
		if row.voucher_type == invoice_doctype:
			continue  # the invoice itself, or a return booked against it (counted below)
		settled = -flt(row.amount_in_account_currency) * sign
		paid += to_invoice_currency(settled, row.account_currency, details)

	# Returns may carry their own outstanding (ERPNext's "update outstanding for self"), so read them directly.
	credited = -sum(
		flt(value)
		for value in frappe.get_all(
			invoice_doctype,
			filters={"return_against": invoice, "is_return": 1, "docstatus": 1},
			pluck="grand_total",
		)
	)
	return frappe._dict(paid=flt(paid, 2), credited=flt(credited, 2), grand_total=flt(details.grand_total))


def to_invoice_currency(amount: float, account_currency: str, invoice) -> float:
	if account_currency == invoice.currency:
		return amount
	return amount / flt(invoice.conversion_rate or 1)


def update_shipping_bill_realisation(name: str) -> None:
	shipping_bill = frappe.get_doc("Shipping Bill", name)
	if shipping_bill.docstatus != 1 or shipping_bill.realisation_status == "Not Required":
		return

	value_per_invoice = {}
	for row in shipping_bill.items:
		if row.sales_invoice:
			value_per_invoice[row.sales_invoice] = value_per_invoice.get(row.sales_invoice, 0) + flt(
				row.invoice_value
			)

	realised = credited = 0.0
	for invoice, value in value_per_invoice.items():
		settlement = get_invoice_settlement("Sales Invoice", invoice)
		share = value / settlement.grand_total if settlement.grand_total else 0
		realised += settlement.paid * share
		credited += settlement.credited * share

	written_off = sum(flt(row.write_off_value) for row in shipping_bill.realisation_actions)
	commission = flt(shipping_bill.get("agency_commission"))
	outstanding = flt(shipping_bill.total_invoice_value) - credited - realised - written_off - commission
	extensions = [
		getdate(row.extended_upto) for row in shipping_bill.realisation_actions if row.extended_upto
	]
	base_due = add_months(
		shipping_bill.shipping_bill_date,
		frappe.db.get_single_value("India EXIM Settings", "export_realisation_months") or 9,
	)

	if outstanding <= TOLERANCE:
		status = "Written Off" if written_off and realised <= TOLERANCE else "Fully Realised"
	elif realised > TOLERANCE or written_off:
		status = "Partly Realised"
	else:
		status = "Pending"

	from india_exim.export_incentives.accounting import sync_incentive_reversal

	sync_incentive_reversal(shipping_bill, credited + written_off)
	shipping_bill.db_set(
		{
			"realised_value": flt(realised, 2),
			"credit_note_value": flt(credited, 2),
			"outstanding_value": flt(max(outstanding, 0), 2),
			"realisation_status": status,
			"realisation_due_date": max([getdate(base_due), *extensions]),
		}
	)


def update_bill_of_entry_payment(name: str) -> None:
	bill_of_entry = frappe.get_doc("Bill of Entry", name)
	if bill_of_entry.docstatus != 1:
		return

	value_per_invoice = {}
	for item in bill_of_entry.items:
		if item.purchase_invoice:
			value_per_invoice.setdefault(item.purchase_invoice, 0)
			value_per_invoice[item.purchase_invoice] += flt(item.get("exim_value_fc"))

	invoice_value = paid = 0.0
	for invoice, value in value_per_invoice.items():
		settlement = get_invoice_settlement("Purchase Invoice", invoice)
		value = value or settlement.grand_total  # duty not calculated here: assume the whole invoice
		share = value / settlement.grand_total if settlement.grand_total else 0
		invoice_value += value
		paid += settlement.paid * share

	if paid >= invoice_value - TOLERANCE and invoice_value:
		status = "Paid"
	elif paid > TOLERANCE:
		status = "Partly Paid"
	else:
		status = "Unpaid"

	months = frappe.db.get_single_value("India EXIM Settings", "import_payment_months") or 6
	bill_of_entry.db_set(
		{
			"exim_invoice_value": flt(invoice_value, 2),
			"exim_paid_value": flt(paid, 2),
			"exim_payment_status": status,
			"exim_payment_due_date": add_months(bill_of_entry.bill_of_entry_date, months),
		}
	)


def get_referenced_invoices(doc) -> dict[str, set[str]]:
	invoices = {"Sales Invoice": set(), "Purchase Invoice": set()}
	if doc.doctype == "Payment Entry":
		rows = [(row.reference_doctype, row.reference_name) for row in doc.references]
	elif doc.doctype == "Journal Entry":
		rows = [(row.reference_type, row.reference_name) for row in doc.accounts]
	else:
		rows = (
			[(doc.doctype, doc.return_against)] if doc.get("is_return") and doc.get("return_against") else []
		)

	for doctype, name in rows:
		if doctype in invoices and name:
			invoices[doctype].add(name)
	return invoices


def refresh_for_invoices(invoices: dict[str, set[str]]) -> None:
	for invoice in invoices["Sales Invoice"]:
		for name in set(
			frappe.get_all(
				"Shipping Bill Item", filters={"sales_invoice": invoice, "docstatus": 1}, pluck="parent"
			)
		):
			update_shipping_bill_realisation(name)
	for invoice in invoices["Purchase Invoice"]:
		for name in set(
			frappe.get_all(
				"Bill of Entry Item", filters={"purchase_invoice": invoice, "docstatus": 1}, pluck="parent"
			)
		):
			update_bill_of_entry_payment(name)


def on_settlement_change(doc, method=None):
	"""doc_event for Payment Entry, Journal Entry and returns: refresh the affected EXIM documents."""
	refresh_for_invoices(get_referenced_invoices(doc))


def refresh_open_documents() -> None:
	"""Daily safety net, e.g. after Payment Reconciliation or unreconcile."""
	for name in frappe.get_all(
		"Shipping Bill",
		filters={"docstatus": 1, "realisation_status": ("in", ("Pending", "Partly Realised"))},
		pluck="name",
	):
		update_shipping_bill_realisation(name)
	for name in frappe.get_all(
		"Bill of Entry", filters={"docstatus": 1, "exim_payment_status": ("!=", "Paid")}, pluck="name"
	):
		update_bill_of_entry_payment(name)
