import frappe


def validate(doc, method=None):
	"""Default the customs tariff from the GST HSN code when an 8-digit tariff with that code exists."""
	if doc.get("exim_customs_tariff_item") or not doc.get("gst_hsn_code"):
		return
	if len(doc.gst_hsn_code) == 8 and frappe.db.exists("Customs Tariff Item", doc.gst_hsn_code):
		doc.exim_customs_tariff_item = doc.gst_hsn_code
