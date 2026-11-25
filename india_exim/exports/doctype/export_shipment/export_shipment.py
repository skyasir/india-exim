# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from india_exim.trade_documents.checklist import (
	apply_checklist,
	enforce_gate,
	get_readiness,
	get_shipping_bills,
	refresh_due_dates,
	sync_system_documents,
)
from india_exim.utils.item_details import get_item_details, get_packing

AUTOMATIC_STATUSES = ("Planned", "Booked", "Stuffed", "Customs Cleared", "Shipped")
GATED_STATUSES = ("Documents Sent", "Delivered", "Closed")


class ExportShipment(Document):
	def validate(self):
		self.validate_invoices()
		self.set_handling_from_items()
		self.set_totals()
		if self.is_new() and not self.documents:
			apply_checklist(self)
		refresh_due_dates(self)
		sync_system_documents(self)
		self.readiness_percent = get_readiness(self)
		self.advance_status()
		if self.status in GATED_STATUSES and self.has_value_changed("status"):
			enforce_gate(self, _("Shipment moved to {0}").format(_(self.status)))

	def on_update(self):
		"""Shipping bills made before the shipment join it, and get its transport document."""
		before = self.get_doc_before_save()
		for bill in get_shipping_bills(self):
			values = {}
			if not bill.export_shipment:
				values["export_shipment"] = self.name
			if self.bl_number and bill.bl_number in (None, "", before and before.bl_number):
				values.update(bl_number=self.bl_number, bl_date=self.bl_date)
			if values:
				# silent: this also runs while the shipping bill itself is being saved
				frappe.db.set_value("Shipping Bill", bill.name, values, update_modified=False)

	def advance_status(self):
		"""Move the status to the furthest step whose record exists. Never backwards, and the steps
		after Shipped stay with the user, so a status set by hand is kept."""
		if self.status not in AUTOMATIC_STATUSES:
			return
		reached = "Planned"
		if self.booking_number:
			reached = "Booked"
		if any(row.container_number for row in self.containers):
			reached = "Stuffed"
		if any(bill.leo_date for bill in get_shipping_bills(self)):
			reached = "Customs Cleared"
		if self.atd or self.bl_number:
			reached = "Shipped"
		if AUTOMATIC_STATUSES.index(reached) > AUTOMATIC_STATUSES.index(self.status):
			self.status = reached

	def validate_invoices(self):
		seen = set()
		for row in self.invoices:
			if row.sales_invoice in seen:
				frappe.throw(
					_("Row {0}: Sales Invoice {1} is listed twice.").format(row.idx, row.sales_invoice)
				)
			seen.add(row.sales_invoice)
			details = frappe.db.get_value(
				"Sales Invoice",
				row.sales_invoice,
				["company", "customer", "docstatus", "currency"],
				as_dict=True,
			)
			if details.docstatus == 2:
				frappe.throw(_("Row {0}: Sales Invoice {1} is cancelled.").format(row.idx, row.sales_invoice))
			if (details.company, details.customer) != (self.company, self.customer):
				frappe.throw(
					_("Row {0}: Sales Invoice {1} belongs to a different company or customer.").format(
						row.idx, row.sales_invoice
					)
				)
			self.currency = self.currency or details.currency

	def get_invoice_items(self) -> list:
		invoices = [row.sales_invoice for row in self.invoices if row.sales_invoice]
		if not invoices:
			return []
		return frappe.get_all(
			"Sales Invoice Item",
			filters={"parent": ("in", invoices), "parenttype": "Sales Invoice"},
			fields=["item_code", "stock_qty"],
		)

	def set_handling_from_items(self):
		"""Dangerous goods and temperature control come from the items' Export & Import tab:
		ticked when any item needs it, UN numbers and temperatures filled when left empty."""
		un_numbers, temperatures = [], []
		dangerous = reefer = False
		for item_code in dict.fromkeys(row.item_code for row in self.get_invoice_items()):
			item = get_item_details(item_code)
			if item.exim_is_dangerous_goods:
				dangerous = True
				if item.exim_un_number and item.exim_un_number not in un_numbers:
					un_numbers.append(item.exim_un_number)
			if item.exim_is_reefer:
				reefer = True
				if item.exim_temperature_setting and item.exim_temperature_setting not in temperatures:
					temperatures.append(item.exim_temperature_setting)
		if dangerous:
			self.is_dangerous_goods = 1
			self.un_number = self.un_number or ", ".join(un_numbers)
		if reefer:
			self.is_reefer = 1
			self.temperature_setting = self.temperature_setting or ", ".join(temperatures)

	def set_totals(self):
		if self.containers:
			self.total_gross_weight = sum(flt(row.gross_weight) for row in self.containers)
			self.total_packages = sum(int(row.packages or 0) for row in self.containers)
		else:
			# until containers are stuffed, estimate from the items' packing details
			packing = [get_packing(row.item_code, row.stock_qty) for row in self.get_invoice_items()]
			self.total_gross_weight = sum(flt(row.gross_weight) for row in packing)
			self.total_packages = sum(row.packages for row in packing)
		self.total_charges = sum(flt(row.amount) for row in self.charges)


@frappe.whitelist()
def refresh_document_checklist(name: str) -> dict:
	shipment = frappe.get_doc("Export Shipment", name)
	shipment.check_permission("write")
	added = apply_checklist(shipment)
	shipment.save()
	return {"added": added, "total": len(shipment.documents)}


@frappe.whitelist()
def make_shipping_bill(source_name: str) -> Document:
	"""New Shipping Bill with all submitted invoices of this shipment."""
	from india_exim.exports.doctype.shipping_bill.shipping_bill import get_items_from_sales_invoices

	shipment = frappe.get_doc("Export Shipment", source_name)
	shipment.check_permission("read")
	invoices = [
		row.sales_invoice
		for row in shipment.invoices
		if frappe.db.get_value("Sales Invoice", row.sales_invoice, "docstatus") == 1
	]
	if not invoices:
		frappe.throw(_("Add at least one submitted Sales Invoice to the shipment first."))

	first_invoice = frappe.get_doc("Sales Invoice", invoices[0])
	# freight and insurance in the invoice value (CIF, CFR...) are deducted to reach FOB
	charges = frappe.get_all(
		"Sales Invoice",
		filters={"name": ("in", invoices)},
		fields=[{"SUM": "exim_freight", "as": "freight"}, {"SUM": "exim_insurance", "as": "insurance"}],
	)[0]
	shipping_bill = frappe.new_doc("Shipping Bill")
	shipping_bill.update(
		{
			"company": shipment.company,
			"customer": shipment.customer,
			"export_shipment": shipment.name,
			"currency": first_invoice.currency,
			"incoterm": shipment.incoterm,
			"destination_country": shipment.destination_country,
			"port_code": shipment.port_of_loading,
			"freight": charges.freight,
			"insurance": charges.insurance,
			"shipping_bill_date": frappe.utils.today(),
			"export_type": "With Payment of IGST"
			if first_invoice.get("is_export_with_gst")
			else "Under LUT / Bond (without IGST)",
		}
	)
	for row in get_items_from_sales_invoices(invoices):
		shipping_bill.append("items", row)
	return shipping_bill
