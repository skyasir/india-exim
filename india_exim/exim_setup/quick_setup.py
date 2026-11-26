"""Quick Setup: the few things a company must tell India EXIM before its first export."""

import frappe
from frappe import _
from frappe.utils import cint

from india_exim.exim_setup.doctype.port_master.port_master import get_ad_codes
from india_exim.features import BUSINESS_TYPES, FEATURES, get_features
from india_exim.setup.accounts import setup_exim_accounts


@frappe.whitelist()
def get_setup(company: str) -> dict:
	"""What is already known, to fill the dialog with."""
	frappe.only_for(("System Manager", "EXIM Manager"))
	ad = next(iter(get_ad_codes(company, fields=("ad_code", "bank"))), None)
	if ad:
		ad.port_code = ad.parent
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
		"business_type": settings.business_type or "Export",
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
		port = frappe.get_doc("Port Master", values.port_code.strip().upper())
		row = next(
			(row for row in port.ad_codes if row.company == company.name and row.ad_code == values.ad_code),
			None,
		)
		if not row:
			port.append(
				"ad_codes",
				{
					"company": company.name,
					"ad_code": values.ad_code,
					"bank": values.bank,
					"is_default": not any(row.company == company.name for row in port.ad_codes),
				},
			)
		elif values.bank and not row.bank:
			row.bank = values.bank
		port.save()
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
	if values.business_type in BUSINESS_TYPES:
		settings.business_type = values.business_type
	for field in FEATURES:
		if field in values:
			settings.set(field, cint(values[field]))
	settings.save()
	return {"done": done, "features": get_features()}
