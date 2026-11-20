# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

"""Export price build-up: ex-works cost -> FOB -> CFR -> CIF, less the incentives the exporter
expects, plus bank charges, ECGC premium and margin, converted to the quote currency.

Shipment-level costs are spread over the lines by their ex-works value. For each line, the price
P (INR) solves

	P x (1 - bank% - ECGC% - margin%) + incentive% x FOB(P) = cost at the Incoterm

where FOB(P) = P less the freight and insurance included in the price, so the margin is earned on
the price after charges, with Drawback and RoDTEP passed to the buyer when that is chosen.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

from india_exim.utils.rates import get_incentive_rate

FREIGHT_TERMS = ("CFR", "CPT", "CIF", "CIP", "DAP", "DPU", "DDP")
INSURANCE_TERMS = ("CIF", "CIP", "DAP", "DPU", "DDP")


class ExportCostingSheet(Document):
	def validate(self):
		if flt(self.exchange_rate) <= 0:
			frappe.throw(_("Exchange Rate must be more than zero."))
		self.set_incentive_rates()
		self.calculate()

	def set_incentive_rates(self):
		for row in self.items:
			for scheme, field in (("Duty Drawback", "drawback_rate"), ("RoDTEP", "rodtep_rate")):
				if row.get(field) or not row.customs_tariff_item:
					continue
				rate = get_incentive_rate(scheme, row.customs_tariff_item, getdate(self.posting_date))
				row.set(field, flt(rate.rate) if rate else 0)

	def calculate(self):
		charges = (
			flt(self.bank_charges_percent) + flt(self.ecgc_premium_percent) + flt(self.margin_percent)
		) / 100
		if charges >= 1:
			frappe.throw(_("Bank charges, ECGC premium and margin together must be less than 100%."))

		exw_total = sum(flt(row.ex_works_cost) * flt(row.qty) for row in self.items)
		fob_costs = (
			flt(self.packing) + flt(self.inland_haulage) + flt(self.port_charges) + flt(self.other_fob_costs)
		)
		freight = flt(self.freight) if self.incoterm in FREIGHT_TERMS else 0
		insurance = flt(self.insurance) if self.incoterm in INSURANCE_TERMS else 0
		on_fob = self.incoterm != "EXW"

		totals = frappe._dict(exw=0, fob=0, basis=0, incentives=0, price=0)
		for row in self.items:
			row.currency = self.currency
			row.exw_amount = flt(row.ex_works_cost) * flt(row.qty)
			share = row.exw_amount / exw_total if exw_total else 1 / len(self.items)
			row.fob_amount = row.exw_amount + (fob_costs * share if on_fob else 0)
			carriage = (freight + insurance) * share
			row.cost_at_basis = row.fob_amount + carriage

			incentive_rate = (
				(flt(row.drawback_rate) + flt(row.rodtep_rate)) / 100 if self.include_incentives else 0
			)
			if self.incoterm == "EXW":
				incentive_rate = 0  # the buyer exports; the incentives are not ours
			price = (row.cost_at_basis + incentive_rate * carriage) / (1 - charges + incentive_rate)
			row.incentive_amount = flt(incentive_rate * (price - carriage), 2)
			row.price_inr = flt(price, 2)
			row.amount_fc = flt(price / flt(self.exchange_rate), 2)
			row.rate_fc = flt(row.amount_fc / flt(row.qty), 4) if flt(row.qty) else 0

			totals.exw += row.exw_amount
			totals.fob += row.fob_amount
			totals.basis += row.cost_at_basis
			totals.incentives += row.incentive_amount
			totals.price += row.price_inr

		self.total_exw = totals.exw
		self.total_fob_cost = totals.fob
		self.total_cost_at_basis = totals.basis
		self.total_incentives = totals.incentives
		self.total_price_inr = totals.price
		self.total_price_fc = flt(totals.price / flt(self.exchange_rate), 2)
		self.margin_amount = flt(totals.price * flt(self.margin_percent) / 100, 2)


@frappe.whitelist()
def update_quotation_rates(name: str) -> int:
	"""Copy the costed rates into the linked draft quotation, line by line on the item."""
	sheet = frappe.get_doc("Export Costing Sheet", name)
	sheet.check_permission("read")
	if not sheet.quotation:
		frappe.throw(_("Link a quotation first."))
	quotation = frappe.get_doc("Quotation", sheet.quotation)
	quotation.check_permission("write")
	if quotation.docstatus != 0:
		frappe.throw(_("Quotation {0} is not a draft.").format(quotation.name))
	if quotation.currency != sheet.currency:
		frappe.throw(
			_("Quotation {0} is in {1}; the costing is in {2}.").format(
				quotation.name, quotation.currency, sheet.currency
			)
		)
	rates = {row.item_code: row.rate_fc for row in sheet.items}
	updated = 0
	for item in quotation.items:
		if item.item_code in rates:
			item.rate = rates[item.item_code]
			updated += 1
	if not updated:
		frappe.throw(_("None of the costed items is on quotation {0}.").format(quotation.name))
	if sheet.incoterm and not quotation.incoterm:
		quotation.incoterm = sheet.incoterm
	quotation.save()
	return updated


@frappe.whitelist()
def make_costing_sheet(source_name: str) -> Document:
	"""New costing sheet from a quotation: its customer, currency, Incoterm and items."""
	quotation = frappe.get_doc("Quotation", source_name)
	quotation.check_permission("read")
	sheet = frappe.new_doc("Export Costing Sheet")
	sheet.update(
		{
			"company": quotation.company,
			"customer": quotation.party_name if quotation.quotation_to == "Customer" else None,
			"quotation": quotation.name,
			"currency": quotation.currency,
			"exchange_rate": quotation.conversion_rate,
			"incoterm": quotation.incoterm or "FOB",
			"destination_country": quotation.get("exim_destination_country"),
		}
	)
	for item in quotation.items:
		sheet.append(
			"items",
			{
				"item_code": item.item_code,
				"item_name": item.item_name,
				"qty": item.qty,
				"uom": item.uom,
				"customs_tariff_item": frappe.db.get_value(
					"Item", item.item_code, "exim_customs_tariff_item"
				),
				"ex_works_cost": flt(item.valuation_rate)
				or flt(frappe.db.get_value("Item", item.item_code, "valuation_rate")),
			},
		)
	return sheet
