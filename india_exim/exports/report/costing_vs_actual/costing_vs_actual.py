# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

"""Export Costing Sheet against what happened: invoiced price, cost of goods delivered, shipment
charges and incentives on the shipping bills, followed through Quotation -> Sales Order ->
Sales Invoice -> Export Shipment / Shipping Bill."""

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters: dict | None = None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns() -> list[dict]:
	currency = {"fieldtype": "Currency", "width": 120}
	return [
		{
			"label": _("Costing Sheet"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Export Costing Sheet",
			"width": 140,
		},
		{
			"label": _("Customer"),
			"fieldname": "customer",
			"fieldtype": "Link",
			"options": "Customer",
			"width": 160,
		},
		{
			"label": _("Quotation"),
			"fieldname": "quotation",
			"fieldtype": "Link",
			"options": "Quotation",
			"width": 140,
		},
		{"label": _("Invoices"), "fieldname": "invoices", "fieldtype": "Data", "width": 160},
		{"label": _("Costed Price"), "fieldname": "costed_price", **currency},
		{"label": _("Invoiced"), "fieldname": "actual_price", **currency},
		{"label": _("Costed Cost"), "fieldname": "costed_cost", **currency},
		{"label": _("Goods Cost"), "fieldname": "actual_goods_cost", **currency},
		{"label": _("Goods Cost Basis"), "fieldname": "goods_cost_basis", "fieldtype": "Data", "width": 150},
		{"label": _("Shipment Charges"), "fieldname": "actual_charges", **currency},
		{"label": _("Charges Basis"), "fieldname": "charges_basis", "fieldtype": "Data", "width": 130},
		{"label": _("Bank and ECGC"), "fieldname": "finance_charges", **currency},
		{"label": _("Costed Incentives"), "fieldname": "costed_incentives", **currency},
		{"label": _("Actual Incentives"), "fieldname": "actual_incentives", **currency},
		{"label": _("Costed Margin"), "fieldname": "costed_margin", **currency},
		{"label": _("Actual Margin"), "fieldname": "actual_margin", **currency},
		{"label": _("Variance"), "fieldname": "variance", **currency},
	]


def get_data(filters) -> list[dict]:
	conditions = {"quotation": ("is", "set")}
	if filters.get("company"):
		conditions["company"] = filters.company
	if filters.get("customer"):
		conditions["customer"] = filters.customer
	if filters.get("from_date") and filters.get("to_date"):
		conditions["posting_date"] = ("between", [filters.from_date, filters.to_date])
	sheets = frappe.get_all(
		"Export Costing Sheet",
		filters=conditions,
		fields=[
			"name",
			"customer",
			"quotation",
			"total_price_inr",
			"total_cost_at_basis",
			"total_incentives",
			"margin_amount",
			"total_exw",
			"bank_charges_percent",
			"ecgc_premium_percent",
		],
		order_by="posting_date desc",
	)
	data = []
	for sheet in sheets:
		invoices = get_invoices(sheet.quotation)
		row = frappe._dict(
			name=sheet.name,
			customer=sheet.customer,
			quotation=sheet.quotation,
			invoices=", ".join(invoices),
			costed_price=sheet.total_price_inr,
			costed_cost=sheet.total_cost_at_basis,
			costed_incentives=sheet.total_incentives,
			costed_margin=sheet.margin_amount,
		)
		if invoices:
			row.actual_price = sum(
				flt(value)
				for value in frappe.get_all(
					"Sales Invoice", filters={"name": ("in", invoices)}, pluck="base_net_total"
				)
			)
			row.actual_goods_cost = get_goods_cost(invoices)
			row.goods_cost_basis = _("Stock valuation")
			if not row.actual_goods_cost:
				# goods without stock valuation (non-stock items, drop-ship): the costed ex-works
				# cost for the quantity actually invoiced, net of returns
				row.actual_goods_cost = get_costed_goods_cost(sheet, invoices)
				row.goods_cost_basis = _("Costed (no valuation)")
			row.actual_charges = get_shipment_charges(invoices)
			row.charges_basis = _("Actual")
			if not row.actual_charges:
				# nothing recorded on the shipment yet: freight, insurance and FOB costs are not free
				row.actual_charges = get_costed_charges(sheet, invoices)
				row.charges_basis = _("Costed (none recorded)")
			# not recorded per shipment, so taken at the costed percentages
			row.finance_charges = (
				row.actual_price * (flt(sheet.bank_charges_percent) + flt(sheet.ecgc_premium_percent)) / 100
			)
			row.actual_incentives = get_incentives(invoices)
			row.actual_margin = (
				row.actual_price
				+ row.actual_incentives
				- row.actual_goods_cost
				- row.actual_charges
				- row.finance_charges
			)
			row.variance = row.actual_margin - flt(row.costed_margin)
		data.append(row)
	return data


def get_invoices(quotation: str) -> list[str]:
	orders = frappe.get_all(
		"Sales Order Item",
		filters={"prevdoc_docname": quotation, "docstatus": 1},
		pluck="parent",
		distinct=True,
	)
	if not orders:
		return []
	return frappe.get_all(
		"Sales Invoice Item",
		filters={"sales_order": ("in", orders), "docstatus": 1},
		pluck="parent",
		distinct=True,
	)


def get_goods_cost(invoices: list[str]) -> float:
	"""Cost of the goods delivered: the invoice line's incoming rate, or its delivery note's."""
	items = frappe.get_all(
		"Sales Invoice Item",
		filters={"parent": ("in", invoices)},
		fields=["incoming_rate", "stock_qty", "dn_detail"],
	)
	dn_rates = dict(
		frappe.get_all(
			"Delivery Note Item",
			filters={"name": ("in", [row.dn_detail for row in items if row.dn_detail] or [""])},
			fields=["name", "incoming_rate"],
			as_list=True,
		)
	)
	return sum(flt(row.incoming_rate or dn_rates.get(row.dn_detail)) * flt(row.stock_qty) for row in items)


def get_costed_goods_cost(sheet, invoices: list[str]) -> float:
	return flt(sheet.total_exw) * get_invoiced_share(sheet, invoices)


def get_costed_charges(sheet, invoices: list[str]) -> float:
	"""Everything costed between ex-works and the Incoterm, for the quantity invoiced."""
	return (flt(sheet.total_cost_at_basis) - flt(sheet.total_exw)) * get_invoiced_share(sheet, invoices)


def get_invoiced_share(sheet, invoices: list[str]) -> float:
	"""Quantity invoiced, net of returns, as a share of the quantity costed."""
	costed_qty = sum(
		flt(qty) for qty in frappe.get_all("Export Costing Item", filters={"parent": sheet.name}, pluck="qty")
	)
	if not costed_qty:
		return 0.0
	invoiced_qty = sum(
		flt(qty)
		for qty in frappe.get_all(
			"Sales Invoice Item", filters={"parent": ("in", invoices)}, pluck="stock_qty"
		)
	)
	return invoiced_qty / costed_qty


def get_shipment_charges(invoices: list[str]) -> float:
	shipments = frappe.get_all(
		"Export Shipment Invoice",
		filters={"sales_invoice": ("in", invoices), "parenttype": "Export Shipment"},
		pluck="parent",
		distinct=True,
	)
	if not shipments:
		return 0.0
	return sum(
		flt(value)
		for value in frappe.get_all(
			"Export Shipment", filters={"name": ("in", shipments)}, pluck="total_charges"
		)
	)


def get_incentives(invoices: list[str]) -> float:
	shipping_bills = frappe.get_all(
		"Shipping Bill Item",
		filters={"sales_invoice": ("in", invoices), "docstatus": 1},
		pluck="parent",
		distinct=True,
	)
	if not shipping_bills:
		return 0.0
	rows = frappe.get_all(
		"Shipping Bill",
		filters={"name": ("in", shipping_bills)},
		fields=[
			f"{prefix}{scheme}{suffix}"
			for scheme in ("drawback", "rodtep", "rosctl")
			for prefix, suffix in (("total_", ""), ("", "_reversed"))
		],
	)
	return sum(
		flt(row[f"total_{scheme}"]) - flt(row[f"{scheme}_reversed"])
		for row in rows
		for scheme in ("drawback", "rodtep", "rosctl")
	)
