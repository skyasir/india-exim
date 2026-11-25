import frappe
from frappe import _

# RBI purpose codes for goods; services have their own, so those are left to the user
GOODS_CODES = {
	("Customer", "settled"): "P0102",  # realisation of export bills sent on collection
	("Customer", "advance"): "P0103",  # advance receipts against export contracts
	("Supplier", "settled"): "S0102",  # payment towards imports, settlement of invoice
	("Supplier", "advance"): "S0101",  # advance payment against imports
}
FLAGS = {"Customer": "exim_is_export", "Supplier": "exim_is_import"}
BILLS = ("Sales Invoice", "Purchase Invoice")


def validate(doc, method=None):
	"""Banks report every foreign remittance to RBI under a purpose code."""
	if doc.docstatus != 0 or doc.get("exim_purpose_code") or doc.party_type not in FLAGS:
		return
	if (doc.party_type, doc.payment_type) not in (("Customer", "Receive"), ("Supplier", "Pay")):
		return  # refunds have their own codes
	home = frappe.get_cached_value("Company", doc.company, "default_currency")
	currency = doc.paid_to_account_currency if doc.payment_type == "Pay" else doc.paid_from_account_currency
	if not currency or currency == home:
		return
	doc.exim_purpose_code = get_purpose_code(doc)
	if not doc.exim_purpose_code:
		frappe.msgprint(
			_("RBI Purpose Code is empty. The bank needs it for this foreign remittance."),
			alert=True,
			indicator="orange",
		)


def get_purpose_code(doc) -> str | None:
	flag = FLAGS[doc.party_type]
	references = [
		row
		for row in doc.get("references") or []
		if row.reference_name and frappe.get_meta(row.reference_doctype).has_field(flag)
	]
	if not references:
		if doc.get("references") or not frappe.db.get_value(doc.party_type, doc.party, flag):
			return None
		return GOODS_CODES[(doc.party_type, "advance")]
	kinds = set()
	for row in references:
		if not frappe.db.get_value(row.reference_doctype, row.reference_name, flag):
			return None
		if is_service(row.reference_doctype, row.reference_name):
			return None
		kinds.add("settled" if row.reference_doctype in BILLS else "advance")
	return GOODS_CODES[(doc.party_type, kinds.pop())] if len(kinds) == 1 else None


def is_service(doctype: str, name: str) -> bool:
	codes = frappe.get_all(f"{doctype} Item", filters={"parent": name}, pluck="gst_hsn_code")
	return any((code or "").startswith("99") for code in codes)
