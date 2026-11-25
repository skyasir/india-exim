# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, cint, flt

from india_exim.trade_documents.checklist import (
	TRANSPORT_DOCUMENTS,
	apply_checklist,
	get_readiness,
	mark_received,
	refresh_due_dates,
)
from india_exim.utils.item_details import get_packing

AUTOMATIC_STATUSES = ("Planned", "Booked", "Shipped", "Arrived", "Customs Cleared")
# Import Shipment field -> Purchase Invoice field kept in step with it
INVOICE_FIELDS = {
	"bl_number": "exim_bl_number",
	"bl_date": "exim_bl_date",
	"igm_number": "exim_igm_number",
	"igm_date": "exim_igm_date",
	"eta": "exim_eta",
	"ata": "exim_ata",
	"free_days": "exim_free_days",
	"free_time_ends": "exim_free_time_ends",
	"port_of_loading": "exim_port_of_loading",
	"port_of_discharge": "exim_port_of_discharge",
	"cha": "exim_cha",
	"origin_country": "exim_origin_country",
}


class ImportShipment(Document):
	def validate(self):
		self.validate_rows("orders", "purchase_order", "Purchase Order")
		self.validate_rows("invoices", "purchase_invoice", "Purchase Invoice")
		self.add_invoices_of_orders()
		self.set_origin_country()
		arrival = self.ata or self.eta
		self.free_time_ends = (
			add_days(arrival, cint(self.free_days)) if arrival and cint(self.free_days) else None
		)
		self.set_totals()
		if self.is_new() and not self.documents:
			apply_checklist(self)
		refresh_due_dates(self)
		self.sync_documents()
		self.readiness_percent = get_readiness(self)
		self.advance_status()

	def on_update(self):
		update_invoices(self)

	def on_trash(self):
		for invoice in self.linked_invoices():
			frappe.db.set_value("Purchase Invoice", invoice, "exim_import_shipment", None)

	def validate_rows(self, table, field, doctype):
		seen = set()
		for row in self.get(table):
			name = row.get(field)
			if name in seen:
				frappe.throw(_("Row {0}: {1} is listed twice.").format(row.idx, name))
			seen.add(name)
			details = frappe.db.get_value(
				doctype, name, ["company", "supplier", "docstatus", "currency"], as_dict=True
			)
			if details.docstatus == 2:
				frappe.throw(_("Row {0}: {1} is cancelled.").format(row.idx, name))
			if (details.company, details.supplier) != (self.company, self.supplier):
				frappe.throw(
					_("Row {0}: {1} belongs to a different company or supplier.").format(row.idx, name)
				)
			self.currency = self.currency or details.currency
		if table == "invoices":
			self.validate_other_shipments()

	def validate_other_shipments(self):
		for row in self.invoices:
			other = frappe.db.get_value("Purchase Invoice", row.purchase_invoice, "exim_import_shipment")
			if other and other != self.name and frappe.db.exists("Import Shipment", other):
				frappe.throw(
					_("Row {0}: Purchase Invoice {1} is already on {2}.").format(
						row.idx, row.purchase_invoice, other
					)
				)

	def add_invoices_of_orders(self):
		"""Submitted invoices made from these orders that are on no shipment yet. An order shipped in
		parts has several shipments, so only when this is its only one."""
		orders = [row.purchase_order for row in self.orders if only_shipment(row.purchase_order, self.name)]
		if not orders:
			return
		listed = {row.purchase_invoice for row in self.invoices}
		for invoice in frappe.get_all(
			"Purchase Invoice Item",
			filters={"purchase_order": ("in", orders), "docstatus": 1, "parenttype": "Purchase Invoice"},
			pluck="parent",
			distinct=True,
		):
			details = frappe.db.get_value(
				"Purchase Invoice", invoice, ["exim_import_shipment", "is_return", "supplier"], as_dict=True
			)
			if (
				invoice not in listed
				and not details.is_return
				and details.supplier == self.supplier
				and details.exim_import_shipment in (None, "", self.name)
			):
				self.append("invoices", {"purchase_invoice": invoice})

	def set_origin_country(self):
		home = frappe.get_cached_value("Company", self.company, "country")
		if self.origin_country and self.origin_country != home:
			return
		country = frappe.db.get_value("Supplier", self.supplier, "country")
		if country and country != home:
			self.origin_country = country

	def linked_invoices(self) -> list[str]:
		return frappe.get_all("Purchase Invoice", {"exim_import_shipment": self.name}, pluck="name")

	def get_items(self) -> list:
		"""What is on board: the invoices' items, or the orders' until there is an invoice."""
		for table, field, child in (
			("invoices", "purchase_invoice", "Purchase Invoice Item"),
			("orders", "purchase_order", "Purchase Order Item"),
		):
			names = [row.get(field) for row in self.get(table)]
			if names:
				return frappe.get_all(
					child, filters={"parent": ("in", names)}, fields=["item_code", "stock_qty"]
				)
		return []

	def set_totals(self):
		if self.containers:
			self.total_gross_weight = sum(flt(row.gross_weight) for row in self.containers)
			self.total_packages = sum(cint(row.packages) for row in self.containers)
		else:
			packing = [get_packing(row.item_code, row.stock_qty) for row in self.get_items()]
			self.total_gross_weight = sum(flt(row.gross_weight) for row in packing)
			self.total_packages = sum(row.packages for row in packing)
		self.total_charges = sum(flt(row.amount) for row in self.charges)

	def sync_documents(self):
		for row in self.invoices:
			details = frappe.db.get_value(
				"Purchase Invoice", row.purchase_invoice, ["bill_no", "bill_date"], as_dict=True
			)
			mark_received(self, "Commercial Invoice", details.bill_no, details.bill_date)
		if self.bl_number:
			mark_received(self, TRANSPORT_DOCUMENTS, self.bl_number, self.bl_date)
		if self.igm_number:
			mark_received(self, "Import General Manifest (IGM) Details", self.igm_number, self.igm_date)
		for bill in self.get_bills_of_entry():
			mark_received(self, "Bill of Entry", bill.bill_of_entry_no, bill.bill_of_entry_date)

	def get_bills_of_entry(self) -> list:
		invoices = [row.purchase_invoice for row in self.invoices]
		names = frappe.get_all(
			"Bill of Entry Item",
			filters={"purchase_invoice": ("in", invoices or [""]), "docstatus": 1},
			pluck="parent",
			distinct=True,
		)
		return frappe.get_all(
			"Bill of Entry",
			filters={"name": ("in", names or [""])},
			fields=["name", "bill_of_entry_no", "bill_of_entry_date"],
		)

	def is_cleared(self) -> bool:
		"""Every invoice is fully on submitted Bills of Entry."""
		invoices = [row.purchase_invoice for row in self.invoices]
		if not invoices or not self.get_bills_of_entry():
			return False
		return not frappe.db.exists(
			"Purchase Invoice Item", {"parent": ("in", invoices), "pending_boe_qty": (">", 0.0001)}
		)

	def advance_status(self):
		"""Furthest step whose record exists. Never backwards; the steps after stay with the user."""
		if self.status not in AUTOMATIC_STATUSES:
			return
		reached = "Planned"
		if self.booking_number:
			reached = "Booked"
		if self.atd or self.bl_number:
			reached = "Shipped"
		if self.ata:
			reached = "Arrived"
		if self.is_cleared():
			reached = "Customs Cleared"
		if AUTOMATIC_STATUSES.index(reached) > AUTOMATIC_STATUSES.index(self.status):
			self.status = reached


def only_shipment(purchase_order: str, name: str | None) -> bool:
	return not frappe.db.exists(
		"Import Shipment Order", {"purchase_order": purchase_order, "parent": ("!=", name or "")}
	)


def update_invoices(shipment) -> None:
	"""The shipment is where transport details are kept; its invoices follow it. Only what the
	shipment has is copied, so a detail known only on the invoice stays."""
	invoices = {row.purchase_invoice for row in shipment.invoices}
	for removed in set(shipment.linked_invoices()) - invoices:
		frappe.db.set_value("Purchase Invoice", removed, "exim_import_shipment", None)
	values = {
		target: shipment.get(source) for source, target in INVOICE_FIELDS.items() if shipment.get(source)
	}
	for invoice in invoices:
		frappe.db.set_value("Purchase Invoice", invoice, {**values, "exim_import_shipment": shipment.name})


def on_purchase_invoice_submit(doc, method=None):
	"""An invoice made from an order on a shipment joins that shipment."""
	if not doc.get("exim_is_import") or doc.is_return or doc.get("exim_import_shipment"):
		return
	orders = {row.purchase_order for row in doc.items if row.get("purchase_order")}
	shipments = set(
		frappe.get_all(
			"Import Shipment Order",
			filters={"purchase_order": ("in", list(orders) or [""]), "parenttype": "Import Shipment"},
			pluck="parent",
		)
	)
	if len(shipments) == 1:
		save_shipment(shipments.pop(), invoice=doc.name)


def on_purchase_invoice_cancel(doc, method=None):
	if not doc.get("exim_import_shipment"):
		return
	shipment = frappe.get_doc("Import Shipment", doc.exim_import_shipment)
	shipment.invoices = [row for row in shipment.invoices if row.purchase_invoice != doc.name]
	shipment.flags.ignore_permissions = True
	shipment.save()
	doc.db_set("exim_import_shipment", None)


def on_bill_of_entry_change(doc, method=None):
	for invoice in {row.purchase_invoice for row in doc.items if row.purchase_invoice}:
		name = frappe.db.get_value("Purchase Invoice", invoice, "exim_import_shipment")
		if name and frappe.db.exists("Import Shipment", name):
			save_shipment(name)


def save_shipment(name: str, invoice: str | None = None) -> None:
	shipment = frappe.get_doc("Import Shipment", name)
	if invoice and invoice not in [row.purchase_invoice for row in shipment.invoices]:
		shipment.append("invoices", {"purchase_invoice": invoice})
	shipment.flags.ignore_permissions = True
	shipment.save()


def new_shipment(source) -> Document:
	shipment = frappe.new_doc("Import Shipment")
	shipment.update(
		{
			"company": source.company,
			"supplier": source.supplier,
			"supplier_name": source.supplier_name,
			"currency": source.currency,
			"incoterm": source.get("incoterm"),
			"origin_country": frappe.db.get_value("Supplier", source.supplier, "country"),
		}
	)
	return shipment


@frappe.whitelist()
def make_from_purchase_order(source_name: str) -> Document:
	order = frappe.get_doc("Purchase Order", source_name)
	order.check_permission("read")
	shipment = new_shipment(order)
	shipment.append("orders", {"purchase_order": order.name})
	return shipment


@frappe.whitelist()
def make_from_purchase_invoice(source_name: str) -> Document:
	invoice = frappe.get_doc("Purchase Invoice", source_name)
	invoice.check_permission("read")
	shipment = new_shipment(invoice)
	for source, target in INVOICE_FIELDS.items():
		if invoice.get(target):
			shipment.set(source, invoice.get(target))
	shipment.append("invoices", {"purchase_invoice": invoice.name})
	for order in dict.fromkeys(row.purchase_order for row in invoice.items if row.get("purchase_order")):
		shipment.append("orders", {"purchase_order": order})
	return shipment


@frappe.whitelist()
def refresh_document_checklist(name: str) -> dict:
	shipment = frappe.get_doc("Import Shipment", name)
	shipment.check_permission("write")
	added = apply_checklist(shipment)
	shipment.save()
	return {"added": added, "total": len(shipment.documents)}
