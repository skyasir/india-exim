# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

"""Duty Drawback and RoDTEP per shipping bill: accrued at LEO, claimed, sanctioned and received."""

import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate, today

SCHEMES = (
	("Duty Drawback", "total_drawback", "drawback_reversed"),
	("RoDTEP", "total_rodtep", "rodtep_reversed"),
	("RoSCTL", "total_rosctl", "rosctl_reversed"),
)


def execute(filters: dict | None = None):
	filters = frappe._dict(filters or {})
	data = get_data(filters)
	return get_columns(), data, None, None, get_summary(data)


def get_columns() -> list[dict]:
	return [
		{
			"label": _("Shipping Bill"),
			"fieldname": "shipping_bill",
			"fieldtype": "Link",
			"options": "Shipping Bill",
			"width": 140,
		},
		{"label": _("SB No."), "fieldname": "shipping_bill_number", "fieldtype": "Data", "width": 100},
		{"label": _("SB Date"), "fieldname": "shipping_bill_date", "fieldtype": "Date", "width": 100},
		{"label": _("LEO Date"), "fieldname": "leo_date", "fieldtype": "Date", "width": 100},
		{
			"label": _("Customer"),
			"fieldname": "customer",
			"fieldtype": "Link",
			"options": "Customer",
			"width": 170,
		},
		{"label": _("Scheme"), "fieldname": "scheme", "fieldtype": "Data", "width": 110},
		{"label": _("Accrued (Net)"), "fieldname": "accrued", "fieldtype": "Currency", "width": 120},
		{"label": _("Reversed"), "fieldname": "reversed", "fieldtype": "Currency", "width": 100},
		{
			"label": _("Claim"),
			"fieldname": "claim",
			"fieldtype": "Link",
			"options": "Export Incentive Claim",
			"width": 140,
		},
		{"label": _("Scroll No."), "fieldname": "scroll_number", "fieldtype": "Data", "width": 100},
		{"label": _("Claim Status"), "fieldname": "claim_status", "fieldtype": "Data", "width": 110},
		{"label": _("Sanctioned"), "fieldname": "sanctioned", "fieldtype": "Currency", "width": 120},
		{"label": _("Short / (Excess)"), "fieldname": "difference", "fieldtype": "Currency", "width": 120},
		{"label": _("Received"), "fieldname": "received", "fieldtype": "Currency", "width": 120},
		{"label": _("Receivable"), "fieldname": "receivable", "fieldtype": "Currency", "width": 120},
		{"label": _("Days Since LEO"), "fieldname": "days_since_leo", "fieldtype": "Int", "width": 110},
	]


def get_data(filters) -> list[dict]:
	conditions = {"docstatus": 1, "company": filters.company, "leo_date": ("is", "set")}
	if filters.from_date and filters.to_date:
		conditions["leo_date"] = ("between", [filters.from_date, filters.to_date])
	if filters.customer:
		conditions["customer"] = filters.customer

	shipping_bills = frappe.get_all(
		"Shipping Bill",
		filters=conditions,
		fields=[
			"name",
			"shipping_bill_number",
			"shipping_bill_date",
			"leo_date",
			"customer",
			"total_drawback",
			"total_rodtep",
			"drawback_reversed",
			"rodtep_reversed",
			"total_rosctl",
			"rosctl_reversed",
		],
		order_by="leo_date, name",
	)
	claims = get_claims([row.name for row in shipping_bills])
	as_on = getdate(today())

	data = []
	for sb in shipping_bills:
		for scheme, field, reversed_field in SCHEMES:
			if filters.scheme and filters.scheme != scheme:
				continue
			reversed_amount = flt(sb.get(reversed_field))
			accrued = flt(sb.get(field)) - reversed_amount
			if not flt(sb.get(field)):
				continue
			claim = claims.get((sb.name, scheme)) or frappe._dict()
			sanctioned = flt(claim.sanctioned_amount) if claim.status not in (None, "Draft") else 0
			received = (
				flt(claim.total_received) * sanctioned / flt(claim.total_sanctioned)
				if flt(claim.total_sanctioned)
				else 0
			)
			row = frappe._dict(
				shipping_bill=sb.name,
				shipping_bill_number=sb.shipping_bill_number,
				shipping_bill_date=sb.shipping_bill_date,
				leo_date=sb.leo_date,
				customer=sb.customer,
				scheme=scheme,
				accrued=accrued,
				reversed=reversed_amount,
				claim=claim.claim,
				scroll_number=claim.scroll_number,
				claim_status=claim.status or _("Not Claimed"),
				sanctioned=sanctioned,
				difference=accrued - sanctioned if sanctioned else 0,
				received=flt(received, 2),
				receivable=flt((sanctioned or accrued) - received, 2),
				days_since_leo=date_diff(as_on, sb.leo_date),
			)
			if filters.pending_only and row.receivable <= 0:
				continue
			data.append(row)
	return data


def get_claims(shipping_bills: list[str]) -> dict:
	if not shipping_bills:
		return {}
	claim = frappe.qb.DocType("Export Incentive Claim")
	item = frappe.qb.DocType("Export Incentive Claim Item")
	rows = (
		frappe.qb.from_(item)
		.join(claim)
		.on(claim.name == item.parent)
		.select(
			item.shipping_bill,
			item.sanctioned_amount,
			claim.name.as_("claim"),
			claim.scheme,
			claim.status,
			claim.scroll_number,
			claim.total_sanctioned,
			claim.total_received,
		)
		.where(item.shipping_bill.isin(shipping_bills))
		.where(claim.docstatus < 2)
	).run(as_dict=True)
	return {(row.shipping_bill, row.scheme): row for row in rows}


def get_summary(data: list[dict]) -> list[dict]:
	accrued = sum(row.accrued for row in data)
	received = sum(row.received for row in data)
	unclaimed = sum(row.accrued for row in data if not row.claim)
	return [
		{"label": _("Accrued"), "value": accrued, "datatype": "Currency", "indicator": "Blue"},
		{"label": _("Received"), "value": received, "datatype": "Currency", "indicator": "Green"},
		{
			"label": _("Not Yet Claimed"),
			"value": unclaimed,
			"datatype": "Currency",
			"indicator": "Orange" if unclaimed else "Green",
		},
		{
			"label": _("Receivable"),
			"value": sum(row.receivable for row in data),
			"datatype": "Currency",
			"indicator": "Red",
		},
	]
