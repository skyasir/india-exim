import frappe
from frappe import _
from frappe.utils import formatdate

from india_exim.utils.rates import get_valid_lut

ZERO_RATED_CATEGORIES = ("Overseas", "SEZ")


def is_zero_rated_export_without_tax(doc) -> bool:
	return (
		doc.get("gst_category") in ZERO_RATED_CATEGORIES
		and not doc.get("is_export_with_gst")
		and not doc.get("is_return")
	)


def validate(doc, method=None):
	set_letter_of_undertaking(doc)


def set_letter_of_undertaking(doc):
	if not is_zero_rated_export_without_tax(doc):
		doc.exim_lut = None
		return

	doc.exim_lut = get_valid_lut(doc.company, doc.posting_date)
	if doc.exim_lut:
		return

	mode = frappe.db.get_single_value("India EXIM Settings", "lut_check") or "Block"
	if mode == "Off":
		return

	message = _(
		"No valid Letter of Undertaking (LUT) exists for {0} on {1}. Zero-rated exports without IGST"
		" need a valid LUT; add one under India EXIM > Letter of Undertaking, or tick"
		" 'Is Export With Payment of GST'."
	).format(frappe.bold(doc.company), formatdate(doc.posting_date))
	if mode == "Block":
		frappe.throw(message, title=_("LUT Required"))
	frappe.msgprint(message, title=_("LUT Required"), indicator="orange")


@frappe.whitelist()
def make_export_shipment(source_name: str):
	invoice = frappe.get_doc("Sales Invoice", source_name)
	invoice.check_permission("read")
	ensure_export_invoice(invoice)
	shipment = frappe.new_doc("Export Shipment")
	shipment.update(
		{
			"company": invoice.company,
			"customer": invoice.customer,
			"incoterm": invoice.get("incoterm"),
			"currency": invoice.currency,
			"port_of_loading": invoice.get("port_code"),
			"port_of_discharge": invoice.get("exim_port_of_discharge"),
			"final_destination": invoice.get("exim_final_destination"),
			"payment_terms_type": invoice.get("exim_payment_terms_type"),
			"mode_of_transport": invoice.get("exim_mode_of_transport") or "Sea FCL",
			"marks_and_numbers": invoice.get("exim_marks_and_numbers"),
			"destination_country": invoice.get("exim_destination_country")
			or (
				frappe.db.get_value("Address", invoice.customer_address, "country")
				if invoice.customer_address
				else None
			),
		}
	)
	shipment.append("invoices", {"sales_invoice": invoice.name})
	return shipment


@frappe.whitelist()
def get_export_status(sales_invoice: str) -> dict:
	"""Read-only summary for the invoice's EXIM tab: shipping bills and shipments covering it."""
	frappe.has_permission("Sales Invoice", "read", sales_invoice, throw=True)
	shipping_bills = frappe.get_all(
		"Shipping Bill",
		filters={
			"name": ("in", get_parents("Shipping Bill Item", "sales_invoice", sales_invoice)),
			"docstatus": ("<", 2),
		},
		fields=[
			"name",
			"shipping_bill_number",
			"shipping_bill_date",
			"status",
			"leo_date",
			"currency",
			"realisation_status",
			"realisation_due_date",
			"outstanding_value",
			"total_drawback",
			"total_rodtep",
		],
	)
	shipments = frappe.get_all(
		"Export Shipment",
		filters={"name": ("in", get_parents("Export Shipment Invoice", "sales_invoice", sales_invoice))},
		fields=["name", "status", "readiness_percent", "etd", "bl_number"],
	)
	return {"shipping_bills": shipping_bills, "shipments": shipments}


def get_parents(child_doctype: str, fieldname: str, value: str) -> list[str]:
	return list(set(frappe.get_all(child_doctype, filters={fieldname: value}, pluck="parent"))) or [""]


def ensure_export_invoice(invoice) -> None:
	if not invoice.get("exim_is_export"):
		frappe.throw(
			_("Tick <b>Is Export</b> on Sales Invoice {0} to create export documents from it.").format(
				invoice.name
			),
			title=_("Not an Export Invoice"),
		)
