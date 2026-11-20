# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

"""Purchases at the concessional 0.1% GST for merchant export: deadline, shipping bill used and
whether proof went back to the supplier (IGST notification 41/2017-Integrated Tax (Rate))."""

import frappe
from frappe import _
from frappe.utils import date_diff, getdate, today


def execute(filters: dict | None = None):
	filters = frappe._dict(filters or {})
	data = get_data(filters)
	return get_columns(), data, None, None, get_summary(data)


def get_columns() -> list[dict]:
	return [
		{
			"label": _("Purchase Invoice"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Purchase Invoice",
			"width": 150,
		},
		{"label": _("Supplier"), "fieldname": "supplier_name", "fieldtype": "Data", "width": 180},
		{"label": _("Supplier Invoice"), "fieldname": "bill_no", "fieldtype": "Data", "width": 120},
		{"label": _("Invoice Date"), "fieldname": "bill_date", "fieldtype": "Date", "width": 100},
		{"label": _("Taxable Value"), "fieldname": "base_net_total", "fieldtype": "Currency", "width": 120},
		{
			"label": _("GST Charged"),
			"fieldname": "base_total_taxes_and_charges",
			"fieldtype": "Currency",
			"width": 110,
		},
		{"label": _("Export By"), "fieldname": "exim_merchant_export_due", "fieldtype": "Date", "width": 100},
		{
			"label": _("Shipping Bill"),
			"fieldname": "exim_merchant_shipping_bill",
			"fieldtype": "Link",
			"options": "Shipping Bill",
			"width": 140,
		},
		{"label": _("SB Date"), "fieldname": "shipping_bill_date", "fieldtype": "Date", "width": 100},
		{
			"label": _("Proof Sent On"),
			"fieldname": "exim_merchant_proof_sent_on",
			"fieldtype": "Date",
			"width": 110,
		},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 150},
	]


def get_data(filters) -> list[dict]:
	conditions = {"docstatus": 1, "exim_merchant_export": 1}
	if filters.get("company"):
		conditions["company"] = filters.company
	if filters.get("supplier"):
		conditions["supplier"] = filters.supplier
	rows = frappe.get_all(
		"Purchase Invoice",
		filters=conditions,
		fields=[
			"name",
			"supplier_name",
			"bill_no",
			"bill_date",
			"posting_date",
			"base_net_total",
			"base_total_taxes_and_charges",
			"exim_merchant_export_due",
			"exim_merchant_shipping_bill",
			"exim_merchant_proof_sent_on",
		],
		order_by="exim_merchant_export_due",
	)
	shipping_dates = dict(
		frappe.get_all(
			"Shipping Bill",
			filters={
				"name": (
					"in",
					[row.exim_merchant_shipping_bill for row in rows if row.exim_merchant_shipping_bill]
					or [""],
				)
			},
			fields=["name", "shipping_bill_date"],
			as_list=True,
		)
	)
	as_on = getdate(today())
	data = []
	for row in rows:
		row.bill_date = row.bill_date or row.posting_date
		row.shipping_bill_date = shipping_dates.get(row.exim_merchant_shipping_bill)
		due = getdate(row.exim_merchant_export_due) if row.exim_merchant_export_due else None
		if row.shipping_bill_date:
			late = due and getdate(row.shipping_bill_date) > due
			row.status = (
				_("Exported Late")
				if late
				else _("Proof Pending")
				if not row.exim_merchant_proof_sent_on
				else _("Complete")
			)
		elif due and due < as_on:
			row.status = _("Overdue ({0} days)").format(date_diff(as_on, due))
		else:
			row.status = _("Awaiting Export")
		if filters.get("open_only") and row.status == _("Complete"):
			continue
		data.append(row)
	return data


def get_summary(data: list[dict]) -> list[dict]:
	overdue = [row for row in data if row.status.startswith(_("Overdue")) or row.status == _("Exported Late")]
	return [
		{"label": _("Purchases"), "value": len(data), "datatype": "Int", "indicator": "Blue"},
		{
			"label": _("Awaiting Export"),
			"value": len([r for r in data if r.status == _("Awaiting Export")]),
			"datatype": "Int",
			"indicator": "Orange",
		},
		{
			"label": _("Overdue or Late"),
			"value": len(overdue),
			"datatype": "Int",
			"indicator": "Red" if overdue else "Green",
		},
	]
