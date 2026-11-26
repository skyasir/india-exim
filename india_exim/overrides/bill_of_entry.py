import frappe
from frappe import _

from india_exim.dgft_licences.authorisation import exempt_taxes, set_igst_foregone, set_row_authorisations
from india_exim.exim_setup.doctype.port_master.port_master import get_indian_port
from india_exim.imports.customs_duty import set_customs_duties


class BillOfEntryEXIM:
	"""Extends India Compliance's Bill of Entry: duty is computed before its taxes and totals."""

	def before_validate(self):
		self.fill_from_purchase_invoice()
		set_row_authorisations(self)
		set_customs_duties(self)
		super().before_validate()
		# IGST is worked out by India Compliance above; what was not charged under a licence is saved
		set_igst_foregone(self)

	def fill_from_purchase_invoice(self):
		"""B/L number and port are already on the import invoice; only empty fields are filled."""
		invoice = next((row.purchase_invoice for row in self.items if row.purchase_invoice), None)
		if not invoice or (self.bill_of_lading_no and self.port_code):
			return
		details = frappe.db.get_value(
			"Purchase Invoice", invoice, ["exim_bl_number", "exim_port_of_discharge"], as_dict=True
		)
		self.bill_of_lading_no = self.bill_of_lading_no or details.exim_bl_number
		self.port_code = self.port_code or get_indian_port(details.exim_port_of_discharge)

	def calculate_totals(self):
		exempt_taxes(self)
		super().calculate_totals()


def on_submit(doc, method=None):
	make_landed_cost_voucher(doc)
	from india_exim.fema.payments import update_bill_of_entry_payment

	update_bill_of_entry_payment(doc.name)


def before_cancel(doc, method=None):
	if doc.get("exim_landed_cost_voucher"):
		voucher = frappe.get_doc("Landed Cost Voucher", doc.exim_landed_cost_voucher)
		if voucher.docstatus == 1:
			voucher.flags.ignore_permissions = True
			voucher.ignore_linked_doctypes = ("Bill of Entry",)
			voucher.cancel()


def make_landed_cost_voucher(doc) -> str | None:
	"""Move customs duty into stock value with India Compliance's own Landed Cost Voucher mapping."""
	if not frappe.db.get_single_value("India EXIM Settings", "capitalise_customs_duty"):
		return None
	if not doc.total_customs_duty:
		return None

	from india_compliance.gst_india.doctype.bill_of_entry.bill_of_entry import (
		get_items_for_landed_cost_voucher,
	)
	from india_compliance.gst_india.doctype.bill_of_entry.bill_of_entry import (
		make_landed_cost_voucher as map_landed_cost_voucher,
	)

	if not get_items_for_landed_cost_voucher(doc):
		return None  # no stock items received yet; the user can create it later from the Bill of Entry

	voucher = map_landed_cost_voucher(doc.name)
	voucher.posting_date = doc.posting_date
	voucher.flags.ignore_permissions = True
	voucher.insert()
	voucher.submit()
	doc.db_set("exim_landed_cost_voucher", voucher.name)
	frappe.msgprint(
		_("Customs duty added to stock value through {0}.").format(
			frappe.utils.get_link_to_form("Landed Cost Voucher", voucher.name)
		),
		alert=True,
	)
	return voucher.name
