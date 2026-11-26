"""Item > Export & Import tab: defaults on save and the tariff summary shown in the tab."""

import frappe
from frappe import _
from frappe.utils import flt, today

from india_exim.utils.rates import get_incentive_rate, get_schedule_entries, get_schedule_serial_numbers

INCENTIVE_SCHEMES = ("RoDTEP", "Duty Drawback", "RoSCTL")


def validate(doc, method=None):
	set_tariff_from_hsn(doc)
	set_erpnext_tariff_number(doc)
	set_uqc_conversion(doc)
	set_package_volume(doc)
	validate_packing(doc)
	validate_drawback_serial(doc)


def set_tariff_from_hsn(doc) -> None:
	"""An 8-digit GST HSN code is the ITC-HS code. Use its tariff item, creating it from India
	Compliance's GST HSN master when India EXIM's tariff data does not have it (e.g. chapters
	outside RoDTEP). The trade policy of a created tariff item is left empty (not checked)."""
	hsn = doc.get("gst_hsn_code")
	if doc.get("exim_customs_tariff_item") or not hsn or len(hsn) != 8 or not hsn.isdigit():
		return
	if not frappe.db.exists("Customs Tariff Item", hsn):
		description = frappe.db.get_value("GST HSN Code", hsn, "description")
		if description is None:
			return
		tariff = frappe.new_doc("Customs Tariff Item")
		tariff.update(
			{
				"tariff_code": hsn,
				"description": description or hsn,
				"gst_hsn_code": hsn,
				"export_policy": "",
				"import_policy": "",
				"data_source": "GST HSN Code (India Compliance)",
			}
		)
		tariff.insert(ignore_permissions=True)
	doc.exim_customs_tariff_item = hsn


def set_erpnext_tariff_number(doc) -> None:
	"""Keep ERPNext's own Customs Tariff Number (Purchasing > Foreign Trade Details) filled from
	the ITC-HS code, so it is not entered twice. A number the user set is left as it is."""
	tariff = doc.get("exim_customs_tariff_item")
	if not tariff or doc.get("customs_tariff_number"):
		return
	if not frappe.db.exists("Customs Tariff Number", tariff):
		frappe.get_doc(
			{
				"doctype": "Customs Tariff Number",
				"tariff_number": tariff,
				# ERPNext's description is a Data field (140 characters); the tariff text can be longer
				"description": (frappe.db.get_value("Customs Tariff Item", tariff, "description") or "")[
					:140
				],
			}
		).insert(ignore_permissions=True)
	doc.customs_tariff_number = tariff


def set_uqc_conversion(doc) -> None:
	# the customs unit is fixed by law for the tariff code
	doc.exim_uqc = (
		frappe.db.get_value("Customs Tariff Item", doc.exim_customs_tariff_item, "uqc")
		if doc.exim_customs_tariff_item
		else None
	)
	if doc.exim_uqc and not flt(doc.exim_uqc_conversion_factor) and doc.exim_uqc == doc.stock_uom:
		doc.exim_uqc_conversion_factor = 1


def set_package_volume(doc) -> None:
	dimensions = (doc.exim_package_length, doc.exim_package_width, doc.exim_package_height)
	doc.exim_package_volume = (
		flt(dimensions[0]) * flt(dimensions[1]) * flt(dimensions[2]) / 1_000_000 if all(dimensions) else 0
	)


def validate_packing(doc) -> None:
	if flt(doc.exim_gross_weight_per_unit) and flt(doc.weight_per_unit) > flt(doc.exim_gross_weight_per_unit):
		frappe.throw(
			_("Gross Weight Per Unit cannot be less than the net Weight Per Unit ({0}).").format(
				flt(doc.weight_per_unit)
			),
			title=_("Export Packing"),
		)


def validate_drawback_serial(doc) -> None:
	if not doc.exim_customs_tariff_item or not doc.exim_claim_drawback:
		return
	serials = get_schedule_serial_numbers("Duty Drawback", doc.exim_customs_tariff_item)
	if doc.exim_drawback_serial_no and doc.exim_drawback_serial_no not in serials:
		frappe.throw(
			_(
				"Drawback Schedule Serial No. {0} has no rate for Tariff Item {1}. Add it under Export Incentives first."
			).format(frappe.bold(doc.exim_drawback_serial_no), frappe.bold(doc.exim_customs_tariff_item)),
			title=_("Export Incentives"),
		)
	if (
		not doc.exim_drawback_serial_no
		and len(serials) > 1
		and not get_incentive_rate("Duty Drawback", doc.exim_customs_tariff_item, today(), item_code=doc.name)
	):
		frappe.msgprint(
			_(
				"The drawback schedule has {0} entries for heading {1}. Pick the one for this item under Export Incentives; no drawback is calculated until then."
			).format(len(serials), doc.exim_customs_tariff_item[:4]),
			title=_("Export Incentives"),
			indicator="orange",
		)


@frappe.whitelist()
def get_tariff_summary(customs_tariff_item: str, drawback_serial_no: str | None = None) -> dict:
	"""Trade policy and the duty and incentive rates in force today, for the Item tab."""
	frappe.has_permission("Customs Tariff Item", "read", customs_tariff_item, throw=True)
	tariff = frappe.db.get_value(
		"Customs Tariff Item",
		customs_tariff_item,
		["description", "uqc", "export_policy", "import_policy", "is_scomet", "policy_notes"],
		as_dict=True,
	)
	if not tariff:
		return {}
	duty = frappe.get_all(
		"Customs Tariff Rate",
		filters={
			"parent": customs_tariff_item,
			"parenttype": "Customs Tariff Item",
			"effective_from": ("<=", today()),
		},
		or_filters=[["effective_to", "is", "not set"], ["effective_to", ">=", today()]],
		fields=["bcd_rate", "sws_rate", "aidc_rate", "other_duty_rate", "effective_from"],
		order_by="effective_from desc",
		limit=1,
	)
	incentives = {}
	for scheme in INCENTIVE_SCHEMES:
		serial = drawback_serial_no if scheme == "Duty Drawback" else None
		rate = get_incentive_rate(scheme, customs_tariff_item, today(), serial)
		if rate:
			incentives[scheme] = {
				"rate": rate.rate,
				"amount_per_unit": rate.amount_per_unit,
				"cap_per_unit": rate.cap_per_unit,
				"cap_uom": rate.cap_uom,
				"schedule_serial_no": rate.schedule_serial_no,
				"notified": get_notified_text(scheme, customs_tariff_item, rate),
			}
	return {
		**tariff,
		"duty": duty[0] if duty else None,
		"incentives": incentives,
		"drawback_serials": get_serial_options(customs_tariff_item),
	}


def get_serial_options(customs_tariff_item: str) -> list[dict]:
	descriptions = {
		row.schedule_serial_no: row.description
		for row in get_schedule_entries("Duty Drawback", customs_tariff_item, today())
	}
	options = []
	for serial in get_schedule_serial_numbers("Duty Drawback", customs_tariff_item):
		# the heading's own title is the same for every entry
		text = (descriptions.get(serial) or "").split(" > ", 1)[-1]
		options.append({"value": serial, "label": f"{serial}: {text}" if text else serial})
	return options


def get_notified_text(scheme: str, customs_tariff_item: str, rate) -> str | None:
	"""The notified rate, when the rate in force was entered by hand and differs from it."""
	from india_exim.setup.tariff_data import describe, differs_from_notified

	notified = differs_from_notified(
		frappe._dict(rate, scheme=scheme, customs_tariff_item=customs_tariff_item), today()
	)
	return describe(notified) if notified else None
