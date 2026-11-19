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
	shipment = frappe.new_doc("Export Shipment")
	shipment.update(
		{
			"company": invoice.company,
			"customer": invoice.customer,
			"incoterm": invoice.get("incoterm"),
			"currency": invoice.currency,
			"port_of_loading": invoice.get("port_code"),
			"destination_country": frappe.db.get_value("Address", invoice.customer_address, "country")
			if invoice.customer_address
			else None,
		}
	)
	shipment.append("invoices", {"sales_invoice": invoice.name})
	return shipment
