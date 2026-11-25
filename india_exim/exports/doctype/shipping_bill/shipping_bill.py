# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate
from india_compliance.gst_india.constants import PORT_CODES

from india_exim.dgft_licences.authorisation import apply_to_shipping_bill, on_customs_document_change
from india_exim.exim_setup.doctype.ad_code_registration.ad_code_registration import get_ad_code, get_only_port
from india_exim.export_incentives.accounting import cancel_accrual, make_incentive_accrual
from india_exim.fema.payments import update_shipping_bill_realisation
from india_exim.fema.periods import EXPORT_REALISATION, get_due_date
from india_exim.overrides.sales_invoice import ensure_export_invoice
from india_exim.trade_documents.checklist import update_shipment_from_shipping_bill
from india_exim.utils.item_details import get_item_details, get_quantity_in, get_uqc
from india_exim.utils.rates import (
	get_customs_exchange_rate,
	get_incentive_rate,
	get_rosctl_rate,
	get_schedule_entries,
	get_schedule_serial_numbers,
	warn_stale_exchange_rate,
)

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
		self.set_export_shipment()
		self.validate_drawback_serials()
		self.customs_exchange_rate = get_customs_exchange_rate(
			self.currency, self.shipping_bill_date, "Export"
		)
		self.calculate_fob()
		if self.docstatus == 0:
			warn_stale_exchange_rate(self.currency, self.shipping_bill_date)
			self.warn_missing_details()
		apply_to_shipping_bill(self)
		if not self.accrual_journal_entry:
			self.calculate_incentives(self.leo_date or self.shipping_bill_date)
			if self.docstatus == 0:
				self.warn_unpicked_drawback()
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

		self.validate_not_billed_twice()

	def validate_not_billed_twice(self):
		"""Goods of one invoice may go on several shipping bills, but not for more than was invoiced:
		FOB, realisation and incentives would be counted twice."""
		for (invoice, item_code), qty in sum_quantities(self.items).items():
			invoiced = get_invoiced_quantities([invoice]).get((invoice, item_code))
			if invoiced is None:
				continue
			billed, bills = get_billed_quantity(invoice, item_code, exclude=self.name)
			if bills and billed + qty - invoiced > 0.0001:
				frappe.throw(
					_(
						"{0} of Sales Invoice {1} is already on {2}. Invoiced {3}, already on shipping bills {4}."
					).format(
						frappe.bold(item_code),
						frappe.bold(invoice),
						", ".join(frappe.utils.get_link_to_form("Shipping Bill", name) for name in bills),
						flt(invoiced),
						flt(billed),
					),
					title=_("Already on a Shipping Bill"),
				)

	def validate_drawback_serials(self):
		for row in self.items:
			serial = row.drawback_serial_no
			if not serial or not row.customs_tariff_item:
				continue
			# an entry of the heading on any date (the bill can be older than today's schedule), or the code's own
			if (
				serial.startswith(row.customs_tariff_item[:4])
				and frappe.db.exists("Export Incentive Rate", {"schedule_serial_no": serial})
			) or serial in get_schedule_serial_numbers("Duty Drawback", row.customs_tariff_item):
				continue
			frappe.throw(
				_("Row {0}: {1} is not a drawback schedule entry of tariff item {2}.").format(
					row.idx, frappe.bold(serial), frappe.bold(row.customs_tariff_item)
				)
			)

	def set_export_shipment(self):
		"""The shipment these invoices already belong to."""
		invoices = [row.sales_invoice for row in self.items if row.sales_invoice]
		if self.export_shipment or not invoices:
			return
		shipments = frappe.get_all(
			"Export Shipment Invoice",
			filters={"sales_invoice": ("in", invoices), "parenttype": "Export Shipment"},
			pluck="parent",
		)
		self.export_shipment = frappe.db.get_value(
			"Export Shipment", {"name": ("in", shipments or [""]), "status": ("!=", "Cancelled")}
		)

	def warn_missing_details(self):
		if not self.ad_code:
			frappe.msgprint(
				_(
					"No AD code is registered for port {0}. Customs needs it to credit drawback and GST refunds. Add it under {1}."
				).format(
					self.port_code,
					f'<a href="/desk/ad-code-registration/new?port_code={self.port_code}">{_("AD Code Registration")}</a>',
				),
				title=_("AD Code Missing"),
				indicator="orange",
			)
		if not self.incoterm or self.incoterm in FOB_TYPE_INCOTERMS:
			return
		missing = []
		if not flt(self.freight):
			missing.append(_("Freight"))
		if self.incoterm in ("CIF", "CIP") and not flt(self.insurance):
			missing.append(_("Insurance"))
		if missing:
			frappe.msgprint(
				_(
					"The price is {0} but {1} is zero, so it stays in the FOB value and the incentives come out too high."
				).format(self.incoterm, " / ".join(missing)),
				title=_("Freight and Insurance"),
				indicator="orange",
			)

	def warn_unpicked_drawback(self):
		"""The drawback schedule has several entries for the heading and none is picked: no drawback."""
		for row in self.items:
			if (
				not (row.claim_drawback or row.claim_rosctl)
				or row.drawback_serial_no
				or flt(row.drawback_amount)
			):
				continue
			entries = get_schedule_entries(
				"Duty Drawback", row.customs_tariff_item, self.leo_date or self.shipping_bill_date
			)
			if len(entries) > 1:
				numbers = [entry.schedule_serial_no for entry in entries]
				frappe.msgprint(
					_(
						"Row {0}: no drawback (or RoSCTL) for {1}. Its heading has {2} entries ({3}); set the Drawback Schedule Serial No. on the row, and on the Item for next time."
					).format(
						row.idx,
						frappe.bold(row.item_code),
						len(numbers),
						", ".join(numbers[:8]) + (", ..." if len(numbers) > 8 else ""),
					),
					title=_("Pick the Drawback Entry"),
					indicator="orange",
				)

	def validate_dates(self):
		for field in ("leo_date", "egm_date"):
			if self.get(field) and getdate(self.get(field)) > getdate():
				frappe.throw(_("{0} cannot be in the future.").format(_(self.meta.get_label(field))))
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
				row.uqc, row.uqc_qty = get_uqc(row.item_code, row.qty)
			elif not row.uqc:
				row.uqc = get_uqc(row.item_code, row.qty)[0]
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
					get_incentive_rate(
						scheme,
						row.customs_tariff_item,
						rate_date,
						row.get("drawback_serial_no") if prefix == "drawback" else None,
						row.item_code,
					)
					if row.get(f"claim_{prefix}")
					else None
				)
				row.set(f"{prefix}_rate", flt(rate.rate) if rate else 0)
				row.set(f"{prefix}_cap", flt(rate.cap_per_unit) if rate else 0)
				row.set(
					f"{prefix}_amount",
					compute_incentive(row.fob_value_inr, rate, self.cap_quantity(row, rate)),
				)
			self.calculate_rosctl(row, rate_date)

	def warn_once(self, message: str, title: str) -> None:
		"""Drawback and RoSCTL of one row ask for the same thing; and only while it is a draft."""
		shown = self.flags.setdefault("warned", set())
		if self.docstatus == 0 and message not in shown:
			shown.add(message)
			frappe.msgprint(message, title=title, indicator="orange")

	def cap_quantity(self, row, rate) -> float:
		"""The quantity in the unit the rate's cap is stated in (Kg, piece, pair...)."""
		if not rate or not (flt(rate.cap_per_unit) or flt(rate.amount_per_unit)):
			return flt(row.uqc_qty)
		quantity = get_quantity_in(row.item_code, rate.cap_uom, row.qty, row.uqc, row.uqc_qty)
		if quantity is None:
			self.warn_once(
				_(
					"Row {0}: the incentive cap is per {1}, but the weight or conversion of {2} to {1} is not set on the item. The customs quantity is used, which may be wrong."
				).format(row.idx, rate.cap_uom, row.item_code),
				_("Incentive Cap"),
			)
			return flt(row.uqc_qty)
		return quantity

	def calculate_rosctl(self, row, rate_date):
		"""Garments and made-ups: State and Central levies, each with its own cap. RoSCTL and RoDTEP
		are not given on the same goods, so RoDTEP gives way."""
		rate = (
			get_rosctl_rate(row.customs_tariff_item, rate_date, row.get("drawback_serial_no"))
			if row.get("claim_rosctl") and row.customs_tariff_item
			else None
		)
		row.rosctl_rate = flt(rate.rate) if rate else 0
		row.rosctl_cap = flt(rate.cap_per_unit) if rate else 0
		row.rosctl_central_rate = flt(rate.central_rate) if rate else 0
		row.rosctl_central_cap = flt(rate.central_cap_per_unit) if rate else 0
		quantity = self.cap_quantity(row, rate)
		central = {"rate": row.rosctl_central_rate, "cap_per_unit": row.rosctl_central_cap}
		row.rosctl_amount = flt(
			compute_incentive(row.fob_value_inr, rate, quantity)
			+ compute_incentive(row.fob_value_inr, frappe._dict(central), quantity),
			2,
		)
		if row.rosctl_amount:
			row.rodtep_rate = row.rodtep_cap = row.rodtep_amount = 0

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
		self.total_rosctl = sum(flt(row.rosctl_amount) for row in self.items)
		self.total_igst = sum(flt(row.igst_amount) for row in self.items)

	def set_realisation_fields(self):
		if self.export_type == FREE_OF_COST:
			self.realisation_status = "Not Required"
			self.realisation_due_date = None
			self.outstanding_value = 0
			return

		self.realisation_due_date = get_due_date(EXPORT_REALISATION, self.shipping_bill_date)
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
	"""Rate % of FOB (INR), or a fixed amount per unit where the schedule notifies one, limited by
	the per-unit cap when the schedule has one. Quantities are in the tariff's UQC."""
	if not rate:
		return 0.0
	if flt(rate.get("amount_per_unit")):
		amount = flt(rate.amount_per_unit) * flt(quantity)
	else:
		amount = flt(fob_value_inr) * flt(rate.rate) / 100
	if flt(rate.cap_per_unit):
		amount = min(amount, flt(rate.cap_per_unit) * flt(quantity))
	return flt(amount, 2)


def claim_default(item: dict, fieldname: str) -> int:
	"""The item's claim tick; claimed when the item has no value (e.g. created before the tick)."""
	value = item.get(fieldname)
	return 1 if value is None else cint(value)


def sum_quantities(rows) -> dict[tuple[str, str], float]:
	totals = {}
	for row in rows:
		if row.sales_invoice:
			key = (row.sales_invoice, row.item_code)
			totals[key] = totals.get(key, 0) + flt(row.qty)
	return totals


def get_invoiced_quantities(invoices: list[str]) -> dict[tuple[str, str], float]:
	totals = {}
	for row in frappe.get_all(
		"Sales Invoice Item",
		filters={"parent": ("in", invoices), "parenttype": "Sales Invoice"},
		fields=["parent", "item_code", "qty", "stock_qty"],
	):
		key = (row.parent, row.item_code)
		totals[key] = totals.get(key, 0) + flt(row.stock_qty or row.qty)
	return totals


def get_billed_quantity(invoice: str, item_code: str, exclude: str | None = None) -> tuple[float, list[str]]:
	"""Quantity of an invoice's item already on other shipping bills, and those bills."""
	rows = frappe.get_all(
		"Shipping Bill Item",
		filters={
			"sales_invoice": invoice,
			"item_code": item_code,
			"parenttype": "Shipping Bill",
			"docstatus": ("<", 2),
			"parent": ("!=", exclude or ""),
		},
		fields=["parent", "qty"],
	)
	return sum(flt(row.qty) for row in rows), list(dict.fromkeys(row.parent for row in rows))


@frappe.whitelist()
def get_items_from_sales_invoices(sales_invoices: list[str] | str) -> list[dict]:
	"""Shipping Bill item rows for the given submitted Sales Invoices."""
	sales_invoices = frappe.parse_json(sales_invoices)
	rows = []
	for invoice in sales_invoices:
		billed = {}
		frappe.has_permission("Sales Invoice", "read", invoice, throw=True)
		doc = frappe.get_doc("Sales Invoice", invoice)
		for item in doc.items:
			invoiced = qty = flt(item.stock_qty or item.qty)
			if item.item_code not in billed:
				billed[item.item_code] = get_billed_quantity(doc.name, item.item_code)[0]
			taken = min(billed[item.item_code], qty)
			billed[item.item_code] -= taken
			qty -= taken
			if qty <= 0 < invoiced:
				continue  # all of it is on another shipping bill
			share = qty / invoiced if invoiced else 1
			tariff = frappe.get_cached_value("Item", item.item_code, "exim_customs_tariff_item")
			uqc, uqc_qty = get_uqc(item.item_code, qty)
			claims = get_item_details(item.item_code)
			rows.append(
				{
					"sales_invoice": doc.name,
					"sales_invoice_item": item.name,
					"item_code": item.item_code,
					"item_name": item.item_name,
					"customs_tariff_item": tariff,
					"qty": qty,
					"uom": item.stock_uom or item.uom,
					"uqc": uqc,
					"uqc_qty": uqc_qty,
					"invoice_value": flt(item.amount * share, 2),
					"igst_amount": flt(flt(item.get("igst_amount")) * share, 2),
					# from the item's Export & Import tab (stated here, since doctype defaults are
					# not applied to rows of a new document opened in the browser)
					"claim_drawback": claim_default(claims, "exim_claim_drawback"),
					"drawback_serial_no": claims.exim_drawback_serial_no,
					"claim_rodtep": claim_default(claims, "exim_claim_rodtep"),
					# only garments and made-ups have a RoSCTL rate
					"claim_rosctl": cint(
						claim_default(claims, "exim_claim_rosctl") and has_rosctl(tariff, doc.posting_date)
					),
				}
			)
	return rows


def has_rosctl(tariff: str | None, on_date) -> bool:
	return bool(
		tariff and (get_schedule_entries("RoSCTL", tariff, on_date) or get_rosctl_rate(tariff, on_date))
	)


@frappe.whitelist()
def get_drawback_entries(customs_tariff_item: str) -> list[dict]:
	"""Schedule entries of a tariff item, with their descriptions, to pick from."""
	from india_exim.overrides.item import get_serial_options

	frappe.has_permission("Shipping Bill", "write", throw=True)
	return get_serial_options(customs_tariff_item)


@frappe.whitelist(methods=["POST"])
def make_incentive_claims(shipping_bill: str) -> list[dict]:
	"""A draft claim for every scheme this shipping bill earned and has not been claimed under yet."""
	from india_exim.export_incentives.doctype.export_incentive_claim.export_incentive_claim import (
		SCHEME_HEADS,
		get_existing_claim,
		net_incentive,
	)

	bill = frappe.get_doc("Shipping Bill", shipping_bill)
	bill.check_permission("read")
	frappe.has_permission("Export Incentive Claim", "create", throw=True)
	if bill.docstatus != 1 or not bill.leo_date:
		frappe.throw(_("Incentives are claimed after the Let Export Order (LEO)."))

	claims = []
	for scheme in SCHEME_HEADS:
		amount = net_incentive(bill, scheme)
		if amount <= 0 or get_existing_claim(bill.name, scheme):
			continue
		claim = frappe.get_doc(
			{
				"doctype": "Export Incentive Claim",
				"company": bill.company,
				"scheme": scheme,
				"items": [{"shipping_bill": bill.name}],
			}
		).insert()
		claims.append({"name": claim.name, "scheme": scheme, "amount": claim.total_expected})
	if not claims:
		frappe.msgprint(_("Everything this shipping bill earned is already claimed."))
	return claims


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
			"port_code": invoice.get("port_code") or get_only_port(invoice.company),
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
	rows = get_items_from_sales_invoices([invoice.name])
	if not rows:
		frappe.throw(_("Everything on Sales Invoice {0} is already on a shipping bill.").format(invoice.name))
	for row in rows:
		shipping_bill.append("items", row)
	return shipping_bill
