# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_months, flt, getdate
from india_compliance.gst_india.constants import PORT_CODES

from india_exim.dgft_licences.authorisation import apply_to_shipping_bill, on_customs_document_change
from india_exim.exim_setup.doctype.ad_code_registration.ad_code_registration import get_ad_code
from india_exim.export_incentives.accounting import cancel_accrual, make_incentive_accrual
from india_exim.fema.payments import update_shipping_bill_realisation
from india_exim.overrides.sales_invoice import ensure_export_invoice
from india_exim.trade_documents.checklist import update_shipment_from_shipping_bill
from india_exim.utils.rates import get_customs_exchange_rate, get_incentive_rate

FOB_TYPE_INCOTERMS = ("EXW", "FCA", "FAS", "FOB")
IGST_ROUTE = "With Payment of IGST"
FREE_OF_COST = "Free of Cost / Sample"
SCHEMES = (("Duty Drawback", "drawback"), ("RoDTEP", "rodtep"))


class ShippingBill(Document):
	def validate(self):
		self.validate_port()
		self.validate_invoices()
		self.validate_dates()
		self.validate_freight_and_insurance()
		self.customs_exchange_rate = get_customs_exchange_rate(
			self.currency, self.shipping_bill_date, "Export"
		)
		self.calculate_fob()
		apply_to_shipping_bill(self)
		if not self.accrual_journal_entry:
			self.calculate_incentives(self.leo_date or self.shipping_bill_date)
		self.calculate_igst()
		self.set_totals()
		self.set_realisation_fields()
		self.set_status()

	def on_submit(self):
		self.set_status(update=True)
		self.update_sales_invoice_export_details()
		self.accrue_incentives_if_due()
		update_shipping_bill_realisation(self.name)
		update_shipment_from_shipping_bill(self)
		on_customs_document_change(self)

	def before_update_after_submit(self):
		self.validate_dates()
		self.set_status()

	def on_update_after_submit(self):
		self.accrue_incentives_if_due()
		update_shipping_bill_realisation(self.name)
		update_shipment_from_shipping_bill(self)

	def on_cancel(self):
		self.ignore_linked_doctypes = ("Journal Entry", "GL Entry", "Payment Ledger Entry")
		cancel_accrual(self)
		self.db_set("status", "Cancelled")
		update_shipment_from_shipping_bill(self)
		on_customs_document_change(self)

	def update_sales_invoice_export_details(self):
		"""Fill India Compliance's shipping bill fields (used in GSTR-1 Table 6A) when they are empty."""
		values = {
			"shipping_bill_number": self.shipping_bill_number,
			"shipping_bill_date": self.shipping_bill_date,
			"port_code": self.port_code,
		}
		for invoice in {row.sales_invoice for row in self.items if row.sales_invoice}:
			current = frappe.db.get_value("Sales Invoice", invoice, list(values), as_dict=True)
			missing = {field: value for field, value in values.items() if not current.get(field)}
			if not missing:
				continue
			frappe.db.set_value("Sales Invoice", invoice, missing)
			frappe.get_doc("Sales Invoice", invoice).add_comment(
				"Info",
				_("Shipping bill details set from {0} for GST returns.").format(
					frappe.utils.get_link_to_form("Shipping Bill", self.name)
				),
			)

	def validate_port(self):
		self.port_code = (self.port_code or "").strip().upper()
		if self.port_code not in PORT_CODES:
			frappe.throw(
				_("{0} is not a valid Indian customs port code.").format(frappe.bold(self.port_code))
			)
		self.port_name = PORT_CODES[self.port_code]
		if not self.ad_code:
			self.ad_code = get_ad_code(self.company, self.port_code)

		if self.shipping_bill_number:
			duplicate = frappe.db.get_value(
				"Shipping Bill",
				{
					"shipping_bill_number": self.shipping_bill_number,
					"port_code": self.port_code,
					"docstatus": ("<", 2),
					"name": ("!=", self.name),
				},
			)
			if duplicate:
				frappe.throw(
					_("Shipping Bill No. {0} at port {1} is already recorded in {2}.").format(
						self.shipping_bill_number, self.port_code, frappe.bold(duplicate)
					)
				)

	def validate_invoices(self):
		for invoice in {row.sales_invoice for row in self.items if row.sales_invoice}:
			details = frappe.db.get_value(
				"Sales Invoice", invoice, ["docstatus", "company", "customer", "currency"], as_dict=True
			)
			if details.docstatus != 1:
				frappe.throw(_("Sales Invoice {0} must be submitted.").format(frappe.bold(invoice)))
			if (details.company, details.customer) != (self.company, self.customer):
				frappe.throw(
					_("Sales Invoice {0} belongs to a different company or customer.").format(
						frappe.bold(invoice)
					)
				)
			if details.currency != self.currency:
				frappe.throw(
					_("Sales Invoice {0} is in {1}; this shipping bill is in {2}.").format(
						frappe.bold(invoice), details.currency, self.currency
					)
				)

	def validate_dates(self):
		if self.leo_date and getdate(self.leo_date) < getdate(self.shipping_bill_date):
			frappe.throw(_("LEO Date cannot be before the Shipping Bill Date."))
		if self.egm_date and not self.leo_date:
			frappe.throw(_("Set the LEO Date before the EGM details."))
		if self.egm_date and getdate(self.egm_date) < getdate(self.leo_date):
			frappe.throw(_("EGM Date cannot be before the LEO Date."))

	def validate_freight_and_insurance(self):
		if self.incoterm in FOB_TYPE_INCOTERMS and (flt(self.freight) or flt(self.insurance)):
			frappe.throw(
				_(
					"Under {0} the invoice value is already FOB, so freight and insurance must not be deducted."
				).format(self.incoterm)
			)
		if flt(self.freight) < 0 or flt(self.insurance) < 0:
			frappe.throw(_("Freight and insurance cannot be negative."))

	def calculate_fob(self):
		total_value = sum(flt(row.invoice_value) for row in self.items)
		if total_value <= 0:
			frappe.throw(_("Total invoice value must be greater than zero."))
		if flt(self.freight) + flt(self.insurance) >= total_value:
			frappe.throw(_("Freight and insurance together cannot exceed the invoice value."))

		precision = self.precision("freight")
		remaining_freight, remaining_insurance = flt(self.freight), flt(self.insurance)
		for index, row in enumerate(self.items):
			row.currency = self.currency
			if not row.uqc_qty:
				row.uqc_qty = row.qty
			if index == len(self.items) - 1:
				row.freight, row.insurance = remaining_freight, remaining_insurance
			else:
				share = flt(row.invoice_value) / total_value
				row.freight = flt(flt(self.freight) * share, precision)
				row.insurance = flt(flt(self.insurance) * share, precision)
				remaining_freight -= row.freight
				remaining_insurance -= row.insurance
			row.fob_value = flt(flt(row.invoice_value) - row.freight - row.insurance, precision)
			row.fob_value_inr = flt(row.fob_value * self.customs_exchange_rate, precision)

	def calculate_incentives(self, rate_date):
		for row in self.items:
			for scheme, prefix in SCHEMES:
				rate = (
					get_incentive_rate(scheme, row.customs_tariff_item, rate_date)
					if row.get(f"claim_{prefix}")
					else None
				)
				row.set(f"{prefix}_rate", flt(rate.rate) if rate else 0)
				row.set(f"{prefix}_cap", flt(rate.cap_per_unit) if rate else 0)
				row.set(f"{prefix}_amount", compute_incentive(row.fob_value_inr, rate, row.uqc_qty))

	def calculate_igst(self):
		for row in self.items:
			if self.export_type != IGST_ROUTE:
				row.igst_amount = 0
			elif flt(row.igst_amount) < 0:
				frappe.throw(_("Row {0}: IGST cannot be negative.").format(row.idx))

	def set_totals(self):
		self.total_invoice_value = sum(flt(row.invoice_value) for row in self.items)
		self.total_fob_value = sum(flt(row.fob_value) for row in self.items)
		self.total_fob_value_inr = sum(flt(row.fob_value_inr) for row in self.items)
		self.total_drawback = sum(flt(row.drawback_amount) for row in self.items)
		self.total_rodtep = sum(flt(row.rodtep_amount) for row in self.items)
		self.total_igst = sum(flt(row.igst_amount) for row in self.items)

	def set_realisation_fields(self):
		if self.export_type == FREE_OF_COST:
			self.realisation_status = "Not Required"
			self.realisation_due_date = None
			self.outstanding_value = 0
			return

		months = frappe.db.get_single_value("India EXIM Settings", "export_realisation_months") or 9
		self.realisation_due_date = add_months(self.shipping_bill_date, months)
		self.outstanding_value = (
			flt(self.total_invoice_value) - flt(self.realised_value) - flt(self.agency_commission)
		)
		if flt(self.agency_commission) and not 0 < flt(self.agency_commission) < flt(
			self.total_invoice_value
		):
			frappe.throw(_("Agency commission must be positive and less than the invoice value."))

	def set_status(self, update=False):
		if self.docstatus == 2:
			status = "Cancelled"
		elif self.docstatus == 0:
			status = "Draft"
		elif self.egm_date:
			status = "EGM Filed"
		elif self.leo_date:
			status = "LEO Granted"
		else:
			status = "Filed"

		if update:
			self.db_set("status", status)
		else:
			self.status = status

	def accrue_incentives_if_due(self):
		if self.accrual_journal_entry or not self.leo_date or self.is_opening:
			return
		if frappe.db.get_single_value("India EXIM Settings", "incentive_accrual_point") != "On LEO":
			return

		self.calculate_incentives(self.leo_date)
		self.set_totals()
		for row in self.items:
			row.db_update()
		self.db_update()
		make_incentive_accrual(self)


def compute_incentive(fob_value_inr, rate, quantity) -> float:
	"""Rate % of FOB (INR), limited by the per-unit cap when the schedule has one."""
	if not rate:
		return 0.0
	amount = flt(fob_value_inr) * flt(rate.rate) / 100
	if flt(rate.cap_per_unit):
		amount = min(amount, flt(rate.cap_per_unit) * flt(quantity))
	return flt(amount, 2)


@frappe.whitelist()
def get_items_from_sales_invoices(sales_invoices: list[str] | str) -> list[dict]:
	"""Shipping Bill item rows for the given submitted Sales Invoices."""
	sales_invoices = frappe.parse_json(sales_invoices)
	rows = []
	for invoice in sales_invoices:
		frappe.has_permission("Sales Invoice", "read", invoice, throw=True)
		doc = frappe.get_doc("Sales Invoice", invoice)
		for item in doc.items:
			rows.append(
				{
					"sales_invoice": doc.name,
					"sales_invoice_item": item.name,
					"item_code": item.item_code,
					"item_name": item.item_name,
					"customs_tariff_item": frappe.db.get_value(
						"Item", item.item_code, "exim_customs_tariff_item"
					),
					"qty": item.stock_qty or item.qty,
					"uom": item.stock_uom or item.uom,
					"invoice_value": item.amount,
					"igst_amount": item.get("igst_amount") or 0,
					# the doctype defaults are not applied to rows opened in the browser as a new
					# document, so state them here
					"claim_drawback": 1,
					"claim_rodtep": 1,
				}
			)
	return rows


@frappe.whitelist()
def make_shipping_bill(source_name: str) -> Document:
	"""New Shipping Bill from one Sales Invoice."""
	invoice = frappe.get_doc("Sales Invoice", source_name)
	invoice.check_permission("read")
	ensure_export_invoice(invoice)
	shipping_bill = frappe.new_doc("Shipping Bill")
	shipping_bill.update(
		{
			"company": invoice.company,
			"customer": invoice.customer,
			"currency": invoice.currency,
			"shipping_bill_date": invoice.get("shipping_bill_date") or invoice.posting_date,
			"shipping_bill_number": invoice.get("shipping_bill_number"),
			"port_code": invoice.get("port_code"),
			"incoterm": invoice.get("incoterm"),
			"freight": invoice.get("exim_freight"),
			"insurance": invoice.get("exim_insurance"),
			"export_type": IGST_ROUTE
			if invoice.get("is_export_with_gst")
			else "Under LUT / Bond (without IGST)",
			"destination_country": invoice.get("exim_destination_country")
			or (
				frappe.db.get_value("Address", invoice.customer_address, "country")
				if invoice.customer_address
				else None
			),
		}
	)
	for row in get_items_from_sales_invoices([invoice.name]):
		shipping_bill.append("items", row)
	return shipping_bill
