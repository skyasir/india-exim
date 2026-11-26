# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_months, flt, getdate, today

from india_exim.trade_agreements.doctype.trade_agreement.trade_agreement import (
	get_partner_countries,
	validate_claim,
)
from india_exim.trade_agreements.origin import check_origin, get_non_originating_materials

# Trade Document Type ticked on the shipment's checklist
CHECKLIST_DOCUMENTS = {
	"Preferential": "Certificate of Origin (Preferential / FTA)",
	"Non-Preferential": "Certificate of Origin (Non-preferential)",
}


class CertificateofOrigin(Document):
	def validate(self):
		self.fill_from_export()
		self.agreement = self.get_agreement()
		self.set_item_values()
		self.set_status()
		self.warn_if_items_do_not_qualify()

	def on_update(self):
		update_checklist(self)

	def on_trash(self):
		if self.status == "Issued" and frappe.db.exists("Export Shipment", self.export_shipment or ""):
			from india_exim.trade_documents.checklist import mark_reopened

			shipment = frappe.get_doc("Export Shipment", self.export_shipment)
			mark_reopened(shipment, CHECKLIST_DOCUMENTS[self.certificate_type], self.certificate_number)
			shipment.flags.ignore_permissions = True
			shipment.save()

	def fill_from_export(self):
		"""Buyer, destination and goods from the shipping bill, or the invoice before there is one."""
		if self.shipping_bill:
			source = frappe.get_doc("Shipping Bill", self.shipping_bill)
			if source.docstatus == 2:
				frappe.throw(_("Shipping Bill {0} is cancelled.").format(self.shipping_bill))
			destination, shipment = source.destination_country, source.export_shipment
			rows = [
				{
					"item_code": row.item_code,
					"item_name": row.item_name,
					"customs_tariff_item": row.customs_tariff_item,
					"qty": row.qty,
					"uom": row.uom,
					"fob_value": row.fob_value_inr,
					"shipping_bill_item": row.name,
				}
				for row in source.items
			]
		elif self.sales_invoice:
			source = frappe.get_doc("Sales Invoice", self.sales_invoice)
			destination, shipment = source.get("exim_destination_country"), None
			rows = [
				{
					"item_code": row.item_code,
					"item_name": row.item_name,
					"customs_tariff_item": row.get("exim_customs_tariff_item"),
					"qty": row.qty,
					"uom": row.uom,
					"fob_value": row.base_net_amount,
				}
				for row in source.items
			]
		else:
			return

		self.company = self.company or source.company
		self.customer = self.customer or source.customer
		self.destination_country = self.destination_country or destination
		self.export_shipment = self.export_shipment or shipment
		if not self.items:
			for row in rows:
				self.append("items", row)

	def get_agreement(self):
		if self.certificate_type != "Preferential":
			self.trade_agreement = None
			return None
		return validate_claim(
			self.trade_agreement,
			self.destination_country,
			self.certificate_date or self.application_date or today(),
			_("Destination Country"),
		)

	def set_item_values(self):
		agreement = self.agreement
		originating = {"India", *(get_partner_countries(agreement.name) if agreement else ())}
		for row in self.items:
			materials = get_non_originating_materials(row, self.company, originating)
			if not row.manual_values:
				if row.shipping_bill_item:
					row.fob_value = flt(
						frappe.db.get_value("Shipping Bill Item", row.shipping_bill_item, "fob_value_inr")
					)
				row.non_originating_value = materials.value
			row.rvc_percent = (
				flt((flt(row.fob_value) - flt(row.non_originating_value)) / flt(row.fob_value) * 100, 2)
				# not worked out without a BOM or the values entered by hand
				if flt(row.fob_value) and (materials.has_bom or row.manual_values)
				else 0
			)
			if not agreement:
				row.origin_criterion, row.qualifies = None, 0
				row.origin_note = materials.note
				continue
			row.origin_criterion = row.origin_criterion or agreement.origin_criterion
			qualifies, note = check_origin(row, materials, agreement)
			if row.origin_criterion != "PSR":
				row.qualifies = int(qualifies)
			row.origin_note = "\n".join(part for part in (note, materials.note) if part)

		self.total_fob_value = sum(flt(row.fob_value) for row in self.items)
		self.all_items_qualify = int(
			bool(agreement and self.items and all(row.qualifies for row in self.items))
		)
		self.valid_upto = (
			add_months(self.certificate_date, agreement.certificate_validity_months or 12)
			if agreement and self.certificate_date
			else None
		)

	def set_status(self):
		if self.is_rejected:
			self.status = "Rejected"
		elif self.certificate_number and self.certificate_date:
			self.status = "Issued"
		elif self.application_number:
			self.status = "Applied"
		else:
			self.status = "Draft"
		if self.certificate_date and self.application_date:
			if getdate(self.certificate_date) < getdate(self.application_date):
				frappe.throw(_("The certificate date is before the application date."))

	def warn_if_items_do_not_qualify(self):
		if not self.agreement or self.status not in ("Applied", "Issued") or self.all_items_qualify:
			return
		rows = ", ".join(str(row.idx) for row in self.items if not row.qualifies)
		frappe.msgprint(
			_(
				"Rows {0} do not show that they meet the rule of origin of {1}. Check them before relying on the certificate: Customs at the destination can deny the concessional duty and ask the issuing agency to verify."
			).format(rows, frappe.bold(self.trade_agreement)),
			indicator="orange",
			alert=True,
		)


def update_checklist(certificate) -> None:
	"""Tick the certificate on its shipment's document checklist, or reopen it."""
	if not certificate.export_shipment or not frappe.db.exists(
		"Export Shipment", certificate.export_shipment
	):
		return
	from india_exim.trade_documents.checklist import mark_received, mark_reopened

	document_type = CHECKLIST_DOCUMENTS[certificate.certificate_type]
	before = certificate.get_doc_before_save()
	shipment = frappe.get_doc("Export Shipment", certificate.export_shipment)
	rows = [(row.status, row.document_number) for row in shipment.documents]

	if before and before.status == "Issued" and certificate.status != "Issued":
		mark_reopened(shipment, CHECKLIST_DOCUMENTS[before.certificate_type], before.certificate_number)
	if certificate.status == "Issued":
		mark_received(shipment, document_type, certificate.certificate_number, certificate.certificate_date)
	elif certificate.status == "Applied":
		for row in shipment.documents:
			if row.document_type == document_type and row.status == "Pending":
				row.status = "Applied"

	if rows != [(row.status, row.document_number) for row in shipment.documents]:
		shipment.flags.ignore_permissions = True
		shipment.save()
