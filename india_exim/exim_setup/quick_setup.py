"""Quick Setup: the few things a company must tell India EXIM before its first export."""

import frappe
from frappe import _
from frappe.utils import cint

from india_exim.features import FEATURES, get_features
from india_exim.setup.accounts import setup_exim_accounts


@frappe.whitelist()
def get_setup(company: str) -> dict:
	"""What is already known, to fill the dialog with."""
	frappe.only_for(("System Manager", "EXIM Manager"))
	ad = frappe.db.get_value(
		"AD Code Registration",
		{"company": company, "disabled": 0},
		["ad_code", "port_code", "bank"],
		as_dict=True,
		order_by="is_default desc",
	)
	lut = frappe.db.get_value(
		"Letter of Undertaking",
		{"company": company},
		["arn", "valid_from", "valid_upto"],
		as_dict=True,
		order_by="valid_upto desc",
	)
	settings = frappe.get_single("India EXIM Settings")
	return {
		"exim_iec": frappe.db.get_value("Company", company, "exim_iec"),
		**(ad or {}),
		**(lut or {}),
		**{field: cint(settings.get(field)) for field in FEATURES},
	}


@frappe.whitelist(methods=["POST"])
def run_setup(values: dict | str) -> dict:
	"""Save the IEC, accounts, AD code, LUT and switches. Records that exist are kept; only what is
	new is added, so it can be run again."""
	frappe.only_for(("System Manager", "EXIM Manager"))
	values = frappe._dict(frappe.parse_json(values))
	company = frappe.get_doc("Company", values.company)
	company.check_permission("write")

	done = []
	if values.exim_iec:
		company.db_set("exim_iec", values.exim_iec.strip().upper())
		done.append(_("IEC"))
	setup_exim_accounts(company.name)
	done.append(_("Accounts"))

	if values.ad_code and values.port_code:
		port_code = values.port_code.strip().upper()
		existing = frappe.db.get_value(
			"AD Code Registration",
			{"company": company.name, "port_code": port_code, "ad_code": values.ad_code},
		)
		if not existing:
			frappe.get_doc(
				{
					"doctype": "AD Code Registration",
					"company": company.name,
					"ad_code": values.ad_code,
					"port_code": port_code,
					"bank": values.bank,
					"is_default": 1,
				}
			).insert()
		elif values.bank and not frappe.db.get_value("AD Code Registration", existing, "bank"):
			doc = frappe.get_doc("AD Code Registration", existing)
			doc.bank = values.bank
			doc.save()
		done.append(_("AD code"))

	if values.arn and values.valid_from and values.valid_upto:
		if not frappe.db.exists("Letter of Undertaking", {"company": company.name, "arn": values.arn}):
			from erpnext.accounts.utils import get_fiscal_year

			frappe.get_doc(
				{
					"doctype": "Letter of Undertaking",
					"company": company.name,
					"fiscal_year": get_fiscal_year(values.valid_from, company=company.name)[0],
					"arn": values.arn,
					"filed_on": values.valid_from,
					"valid_from": values.valid_from,
					"valid_upto": values.valid_upto,
				}
			).insert()
		done.append(_("LUT"))

	settings = frappe.get_single("India EXIM Settings")
	for field in FEATURES:
		if field in values:
			settings.set(field, cint(values[field]))
	settings.save()
	return {"done": done, "features": get_features()}
