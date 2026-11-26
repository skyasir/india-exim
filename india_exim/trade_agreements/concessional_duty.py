"""Concessional (preferential) duty claimed on a Bill of Entry under a trade agreement.

Under CAROTAR 2020 (Customs Administration of Rules of Origin under Trade Agreements Rules) the
importer claiming the concessional rate declares the certificate of origin on the bill of entry and
must hold the origin-related information, to give to Customs on request.
"""

import frappe
from frappe import _
from frappe.utils import add_months, formatdate, getdate

from india_exim.trade_agreements.doctype.trade_agreement.trade_agreement import validate_claim


def validate_bill_of_entry(doc, method=None) -> None:
	if not doc.get("exim_trade_agreement"):
		doc.exim_fta_duty_saved = 0
		return
	agreement = validate_claim(
		doc.exim_trade_agreement, doc.exim_origin_country, doc.bill_of_entry_date, _("Country of Origin")
	)
	if not (doc.exim_coo_number and doc.exim_coo_date):
		frappe.throw(
			_("Enter the Certificate of Origin number and date to claim {0}.").format(agreement.name)
		)
	if doc.bill_of_entry_date and getdate(doc.exim_coo_date) > getdate(doc.bill_of_entry_date):
		frappe.throw(_("The Certificate of Origin is dated after the Bill of Entry."))
	valid_upto = add_months(doc.exim_coo_date, agreement.certificate_validity_months or 12)
	if doc.bill_of_entry_date and getdate(doc.bill_of_entry_date) > getdate(valid_upto):
		frappe.throw(
			_("The Certificate of Origin was valid only up to {0}.").format(formatdate(valid_upto)),
			title=_("Certificate of Origin Expired"),
		)


def before_submit_bill_of_entry(doc, method=None) -> None:
	if doc.get("exim_trade_agreement") and not doc.get("exim_carotar_confirmed"):
		frappe.throw(
			_(
				"Confirm that you hold the origin-related information for {0} (CAROTAR 2020) before submitting. Customs can ask for it, and the concessional duty can be denied without it."
			).format(frappe.bold(doc.exim_trade_agreement)),
			title=_("Origin Information Needed"),
		)
