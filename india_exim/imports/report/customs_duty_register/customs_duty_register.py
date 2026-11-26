# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

"""Customs duty per Bill of Entry item: assessable value, BCD, SWS, AIDC and other duties,
plus the IGST that India Compliance computes on top."""

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters: dict | None = None):
	filters = frappe._dict(filters or {})
	data = get_data(filters)
	return get_columns(), data, None, None, get_summary(data)


def get_columns() -> list[dict]:
	return [
		{
			"label": _("Bill of Entry"),
			"fieldname": "bill_of_entry",
			"fieldtype": "Link",
			"options": "Bill of Entry",
			"width": 140,
		},
		{"label": _("BE No."), "fieldname": "bill_of_entry_no", "fieldtype": "Data", "width": 100},
		{"label": _("BE Date"), "fieldname": "bill_of_entry_date", "fieldtype": "Date", "width": 100},
		{
			"label": _("Port"),
			"fieldname": "port_code",
			"fieldtype": "Link",
			"options": "Port Master",
			"width": 80,
		},
		{
			"label": _("Supplier"),
			"fieldname": "supplier",
			"fieldtype": "Link",
			"options": "Supplier",
			"width": 170,
		},
		{
			"label": _("Purchase Invoice"),
			"fieldname": "purchase_invoice",
			"fieldtype": "Link",
			"options": "Purchase Invoice",
			"width": 140,
		},
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 160},
		{
			"label": _("Tariff Item"),
			"fieldname": "exim_customs_tariff_item",
			"fieldtype": "Link",
			"options": "Customs Tariff Item",
			"width": 110,
		},
		{"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 80},
		{
			"label": _("Assessable Value"),
			"fieldname": "assessable_value",
			"fieldtype": "Currency",
			"width": 130,
		},
		{"label": _("BCD"), "fieldname": "exim_bcd_amount", "fieldtype": "Currency", "width": 110},
		{"label": _("SWS"), "fieldname": "exim_sws_amount", "fieldtype": "Currency", "width": 100},
		{"label": _("AIDC"), "fieldname": "exim_aidc_amount", "fieldtype": "Currency", "width": 100},
		{
			"label": _("Other Duty"),
			"fieldname": "exim_other_duty_amount",
			"fieldtype": "Currency",
			"width": 100,
		},
		{"label": _("Customs Duty"), "fieldname": "customs_duty", "fieldtype": "Currency", "width": 120},
		{"label": _("IGST"), "fieldname": "igst_amount", "fieldtype": "Currency", "width": 110},
		{
			"label": _("Exemption Notification"),
			"fieldname": "exim_exemption_notification",
			"fieldtype": "Data",
			"width": 150,
		},
	]


def get_data(filters) -> list[dict]:
	boe = frappe.qb.DocType("Bill of Entry")
	item = frappe.qb.DocType("Bill of Entry Item")
	query = (
		frappe.qb.from_(item)
		.join(boe)
		.on(boe.name == item.parent)
		.select(
			boe.name.as_("bill_of_entry"),
			boe.bill_of_entry_no,
			boe.bill_of_entry_date,
			boe.port_code,
			item.purchase_invoice,
			item.item_code,
			item.exim_customs_tariff_item,
			item.qty,
			item.assessable_value,
			item.exim_bcd_amount,
			item.exim_sws_amount,
			item.exim_aidc_amount,
			item.exim_other_duty_amount,
			item.customs_duty,
			item.igst_amount,
			item.exim_exemption_notification,
		)
		.where(boe.docstatus == 1)
		.where(boe.company == filters.company)
		.orderby(boe.bill_of_entry_date)
		.orderby(boe.name)
		.orderby(item.idx)
	)
	if filters.from_date and filters.to_date:
		query = query.where(boe.bill_of_entry_date[filters.from_date : filters.to_date])
	if filters.item_code:
		query = query.where(item.item_code == filters.item_code)

	rows = query.run(as_dict=True)
	suppliers = dict(
		frappe.get_all(
			"Purchase Invoice",
			filters={"name": ("in", list({row.purchase_invoice for row in rows if row.purchase_invoice}))},
			fields=["name", "supplier"],
			as_list=True,
		)
	)
	data = []
	for row in rows:
		row.supplier = suppliers.get(row.purchase_invoice)
		if filters.supplier and row.supplier != filters.supplier:
			continue
		data.append(row)
	return data


def get_summary(data: list[dict]) -> list[dict]:
	def total(field):
		return sum(flt(row.get(field)) for row in data)

	return [
		{
			"label": _("Assessable Value"),
			"value": total("assessable_value"),
			"datatype": "Currency",
			"indicator": "Blue",
		},
		{
			"label": _("Customs Duty"),
			"value": total("customs_duty"),
			"datatype": "Currency",
			"indicator": "Red",
		},
		{
			"label": _("IGST (input credit)"),
			"value": total("igst_amount"),
			"datatype": "Currency",
			"indicator": "Green",
		},
	]
