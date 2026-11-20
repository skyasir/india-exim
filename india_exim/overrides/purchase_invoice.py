import frappe
from frappe import _
from frappe.utils import add_days, cint, getdate


def set_free_time_end(doc, method=None):
	"""Detention / demurrage free time runs from actual arrival."""
	arrival = doc.get("exim_ata") or doc.get("exim_eta")
	doc.exim_free_time_ends = (
		add_days(arrival, cint(doc.get("exim_free_days"))) if arrival and doc.get("exim_free_days") else None
	)


def set_merchant_export_due(doc, method=None):
	"""Merchant export at 0.1% GST (IGST notification 41/2017, CGST 40/2017): the goods must be
	exported within 90 days of the supplier's tax invoice."""
	if not doc.get("exim_merchant_export"):
		doc.exim_merchant_export_due = None
		return
	days = frappe.db.get_single_value("India EXIM Settings", "merchant_export_days") or 90
	doc.exim_merchant_export_due = add_days(doc.bill_date or doc.posting_date, days)
	shipping_bill = doc.get("exim_merchant_shipping_bill")
	if not shipping_bill:
		return
	details = frappe.db.get_value(
		"Shipping Bill", shipping_bill, ["docstatus", "company", "shipping_bill_date"], as_dict=True
	)
	if details.docstatus != 1 or details.company != doc.company:
		frappe.throw(
			_("Shipping Bill {0} must be submitted and belong to {1}.").format(shipping_bill, doc.company)
		)
	if getdate(details.shipping_bill_date) > getdate(doc.exim_merchant_export_due):
		frappe.msgprint(
			_(
				"Shipping Bill {0} is dated after the export deadline of {1}. The 0.1% GST concession"
				" may not apply; the supplier may have to charge the full rate."
			).format(shipping_bill, frappe.format(doc.exim_merchant_export_due, {"fieldtype": "Date"})),
			title=_("Merchant Export Deadline Missed"),
			indicator="orange",
		)
