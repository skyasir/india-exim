# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

"""Unrealised export proceeds per shipping bill, aged from the shipping bill date (the RBI's
EDPMS view). Realisation itself is derived from the Payment Ledger by india_exim.fema.payments."""

import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate, today

OPEN_STATUSES = ("Pending", "Partly Realised")
# up to about 15 months, the realisation period RBI allows for exports from 14.11.2025
BUCKETS = ((90, "0-90"), (180, "91-180"), (270, "181-270"), (365, "271-365"), (455, "366-455"))
BEYOND = "455+"


def execute(filters: dict | None = None):
	filters = frappe._dict(filters or {})
	filters.as_on_date = getdate(filters.as_on_date or today())
	data = get_data(filters)
	return get_columns(), data, None, get_chart(data), get_summary(data)


def get_columns() -> list[dict]:
	return [
		{
			"label": _("Shipping Bill"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Shipping Bill",
			"width": 140,
		},
		{"label": _("SB No."), "fieldname": "shipping_bill_number", "fieldtype": "Data", "width": 100},
		{"label": _("SB Date"), "fieldname": "shipping_bill_date", "fieldtype": "Date", "width": 100},
		{
			"label": _("Customer"),
			"fieldname": "customer",
			"fieldtype": "Link",
			"options": "Customer",
			"width": 180,
		},
		{
			"label": _("Destination"),
			"fieldname": "destination_country",
			"fieldtype": "Link",
			"options": "Country",
			"width": 120,
		},
		{"label": _("AD Code"), "fieldname": "ad_code", "fieldtype": "Data", "width": 90},
		{
			"label": _("Currency"),
			"fieldname": "currency",
			"fieldtype": "Link",
			"options": "Currency",
			"width": 70,
		},
		{
			"label": _("Invoice Value"),
			"fieldname": "total_invoice_value",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},
		{
			"label": _("Realised"),
			"fieldname": "realised_value",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 110,
		},
		{
			"label": _("Credit Notes"),
			"fieldname": "credit_note_value",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 110,
		},
		{
			"label": _("Outstanding"),
			"fieldname": "outstanding_value",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},
		{
			"label": _("Outstanding (INR)"),
			"fieldname": "outstanding_inr",
			"fieldtype": "Currency",
			"width": 130,
		},
		{"label": _("Due Date"), "fieldname": "realisation_due_date", "fieldtype": "Date", "width": 100},
		{"label": _("Age (Days)"), "fieldname": "age", "fieldtype": "Int", "width": 90},
		{"label": _("Overdue (Days)"), "fieldname": "overdue_days", "fieldtype": "Int", "width": 110},
		{"label": _("Ageing"), "fieldname": "bucket", "fieldtype": "Data", "width": 90},
		{"label": _("Status"), "fieldname": "realisation_status", "fieldtype": "Data", "width": 120},
	]


def get_data(filters) -> list[dict]:
	conditions = {
		"docstatus": 1,
		"company": filters.company,
		"realisation_status": ("in", OPEN_STATUSES),
		"shipping_bill_date": ("<=", filters.as_on_date),
	}
	for field in ("customer", "destination_country"):
		if filters.get(field):
			conditions[field] = filters.get(field)

	rows = frappe.get_all(
		"Shipping Bill",
		filters=conditions,
		fields=[
			"name",
			"shipping_bill_number",
			"shipping_bill_date",
			"customer",
			"destination_country",
			"ad_code",
			"currency",
			"customs_exchange_rate",
			"total_invoice_value",
			"realised_value",
			"credit_note_value",
			"outstanding_value",
			"realisation_due_date",
			"realisation_status",
		],
		order_by="shipping_bill_date, name",
	)

	data = []
	for row in rows:
		row.age = date_diff(filters.as_on_date, row.shipping_bill_date)
		row.overdue_days = (
			max(date_diff(filters.as_on_date, row.realisation_due_date), 0) if row.realisation_due_date else 0
		)
		row.bucket = get_bucket(row.age)
		# Customs rate is an estimate of the INR value; the actual rate is the one on realisation.
		row.outstanding_inr = flt(row.outstanding_value) * flt(row.customs_exchange_rate)
		if filters.overdue_only and not row.overdue_days:
			continue
		data.append(row)
	return data


def get_bucket(age: int) -> str:
	for limit, label in BUCKETS:
		if age <= limit:
			return label
	return BEYOND


def get_chart(data: list[dict]) -> dict:
	labels = [label for _limit, label in BUCKETS] + [BEYOND]
	totals = dict.fromkeys(labels, 0.0)
	for row in data:
		totals[row.bucket] += flt(row.outstanding_inr)
	return {
		"data": {
			"labels": labels,
			"datasets": [{"name": _("Outstanding (INR)"), "values": list(totals.values())}],
		},
		"type": "bar",
		"fieldtype": "Currency",
	}


def get_summary(data: list[dict]) -> list[dict]:
	outstanding = sum(flt(row.outstanding_inr) for row in data)
	overdue = sum(flt(row.outstanding_inr) for row in data if row.overdue_days)
	return [
		{"label": _("Shipping Bills"), "value": len(data), "datatype": "Int", "indicator": "Blue"},
		{
			"label": _("Outstanding (INR, at customs rate)"),
			"value": outstanding,
			"datatype": "Currency",
			"indicator": "Orange",
		},
		{
			"label": _("Overdue (INR)"),
			"value": overdue,
			"datatype": "Currency",
			"indicator": "Red" if overdue else "Green",
		},
	]
