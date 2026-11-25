# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

"""Exports grouped by destination country, buyer, product (HS) or month: FOB, incentives and
how much is realised. Built on submitted shipping bills, so it matches what customs recorded."""

import frappe
from frappe import _
from frappe.utils import flt, getdate

GROUPS = {
	"Destination Country": ("destination_country", "Link", "Country"),
	"Customer": ("customer", "Link", "Customer"),
	"Tariff Item (HS)": ("customs_tariff_item", "Link", "Customs Tariff Item"),
	"Month": ("month", "Data", None),
}


def execute(filters: dict | None = None):
	filters = frappe._dict(filters or {})
	filters.group_by = filters.group_by or "Destination Country"
	data = get_data(filters)
	return get_columns(filters), data, None, get_chart(data, filters)


def get_columns(filters) -> list[dict]:
	_fieldname, fieldtype, options = GROUPS[filters.group_by]
	return [
		{
			"label": _(filters.group_by),
			"fieldname": "group",
			"fieldtype": fieldtype,
			"options": options,
			"width": 200,
		},
		{"label": _("Shipping Bills"), "fieldname": "shipping_bills", "fieldtype": "Int", "width": 110},
		{"label": _("FOB (INR)"), "fieldname": "fob_inr", "fieldtype": "Currency", "width": 140},
		{"label": _("Share %"), "fieldname": "share", "fieldtype": "Percent", "width": 90},
		{"label": _("Drawback"), "fieldname": "drawback", "fieldtype": "Currency", "width": 120},
		{"label": _("RoDTEP"), "fieldname": "rodtep", "fieldtype": "Currency", "width": 120},
		{"label": _("RoSCTL"), "fieldname": "rosctl", "fieldtype": "Currency", "width": 120},
		{
			"label": _("Incentive % of FOB"),
			"fieldname": "incentive_percent",
			"fieldtype": "Percent",
			"width": 130,
		},
		{"label": _("Realised %"), "fieldname": "realised_percent", "fieldtype": "Percent", "width": 100},
		{
			"label": _("Outstanding (INR, approx.)"),
			"fieldname": "outstanding_inr",
			"fieldtype": "Currency",
			"width": 160,
		},
	]


def get_data(filters) -> list[dict]:
	sb = frappe.qb.DocType("Shipping Bill")
	item = frappe.qb.DocType("Shipping Bill Item")
	query = (
		frappe.qb.from_(item)
		.join(sb)
		.on(sb.name == item.parent)
		.select(
			sb.name,
			sb.shipping_bill_date,
			sb.destination_country,
			sb.customer,
			sb.customs_exchange_rate,
			sb.total_invoice_value,
			sb.realised_value,
			sb.outstanding_value,
			item.customs_tariff_item,
			item.invoice_value,
			item.fob_value_inr,
			item.drawback_amount,
			item.rodtep_amount,
			item.rosctl_amount,
		)
		.where(sb.docstatus == 1)
		.where(sb.company == filters.company)
		.where(sb.shipping_bill_date[getdate(filters.from_date) : getdate(filters.to_date)])
	)
	for field in ("customer", "destination_country"):
		if filters.get(field):
			query = query.where(sb[field] == filters.get(field))
	rows = query.run(as_dict=True)

	fieldname = GROUPS[filters.group_by][0]
	groups, bills = {}, {}
	for row in rows:
		key = (
			getdate(row.shipping_bill_date).strftime("%Y-%m") if fieldname == "month" else row.get(fieldname)
		)
		group = groups.setdefault(
			key,
			frappe._dict(
				group=key or _("Not Set"),
				fob_inr=0,
				drawback=0,
				rodtep=0,
				rosctl=0,
				invoice=0,
				realised=0,
				outstanding_inr=0,
			),
		)
		bills.setdefault(key, set()).add(row.name)
		share = flt(row.invoice_value) / flt(row.total_invoice_value) if flt(row.total_invoice_value) else 0
		group.fob_inr += flt(row.fob_value_inr)
		group.drawback += flt(row.drawback_amount)
		group.rodtep += flt(row.rodtep_amount)
		group.rosctl += flt(row.rosctl_amount)
		group.invoice += flt(row.invoice_value)
		group.realised += flt(row.realised_value) * share
		group.outstanding_inr += flt(row.outstanding_value) * share * flt(row.customs_exchange_rate)

	total_fob = sum(group.fob_inr for group in groups.values()) or 1
	data = []
	for key, group in groups.items():
		group.shipping_bills = len(bills[key])
		group.share = group.fob_inr * 100 / total_fob
		group.incentive_percent = (
			(group.drawback + group.rodtep + group.rosctl) * 100 / group.fob_inr if group.fob_inr else 0
		)
		group.realised_percent = group.realised * 100 / group.invoice if group.invoice else 0
		data.append(group)
	data.sort(key=lambda row: row.group if fieldname == "month" else -row.fob_inr)
	return data


def get_chart(data: list[dict], filters) -> dict | None:
	if not data:
		return None
	rows = data if filters.group_by == "Month" else data[:10]
	return {
		"data": {
			"labels": [str(row.group) for row in rows],
			"datasets": [{"name": _("FOB (INR)"), "values": [flt(row.fob_inr, 2) for row in rows]}],
		},
		"type": "line" if filters.group_by == "Month" else "bar",
		"fieldtype": "Currency",
	}
