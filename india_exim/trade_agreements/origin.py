"""Rules of origin: does an exported product meet the agreement's origin criterion?

Non-originating materials are taken from the product's default BOM. A material is non-originating
when its Country of Origin (Item) is set and is neither India nor a partner country of the agreement
(materials from a partner count as originating: bilateral cumulation, which India's agreements allow).
A material with no Country of Origin is taken as Indian and named in the note, so it can be checked.
"""

import frappe
from frappe import _
from frappe.utils import flt

# digits of the ITC-HS code that must change under a tariff-shift rule
TARIFF_SHIFT = {"CTH": 4, "CTSH": 6}


def get_non_originating_materials(row, company: str | None, originating: set[str]) -> frappe._dict:
	result = frappe._dict(value=0.0, materials=[], has_bom=False, note="")
	bom = frappe.db.get_value(
		"BOM",
		{"item": row.item_code, "is_default": 1, "is_active": 1, "docstatus": 1, "company": company},
		["name", "quantity"],
		as_dict=True,
	)
	if not bom:
		result.note = _("No default BOM for {0}.").format(row.item_code)
		return result

	result.has_bom = True
	units = flt(row.qty) * get_conversion_factor(row.item_code, row.uom) / (flt(bom.quantity) or 1)
	assumed = []
	for material in frappe.get_all(
		"BOM Item",
		filters={"parent": bom.name, "parenttype": "BOM"},
		fields=["item_code", "amount"],
		order_by="idx",
	):
		country, tariff = frappe.db.get_value(
			"Item", material.item_code, ["country_of_origin", "exim_customs_tariff_item"]
		)
		if not country:
			assumed.append(material.item_code)
			continue
		if country in originating:
			continue
		value = flt(flt(material.amount) * units, 2)
		result.value += value
		result.materials.append(
			frappe._dict(item_code=material.item_code, country=country, tariff=tariff, value=value)
		)

	result.value = flt(result.value, 2)
	notes = [_("BOM {0}: {1} non-originating material(s).").format(bom.name, len(result.materials))]
	if assumed:
		notes.append(_("Taken as Indian (no Country of Origin set): {0}.").format(", ".join(assumed)))
	result.note = " ".join(notes)
	return result


def get_conversion_factor(item_code: str, uom: str | None) -> float:
	stock_uom = frappe.get_cached_value("Item", item_code, "stock_uom")
	if not uom or uom == stock_uom:
		return 1.0
	factor = frappe.db.get_value(
		"UOM Conversion Detail", {"parent": item_code, "uom": uom}, "conversion_factor"
	)
	return flt(factor) or 1.0


def check_origin(row, materials: frappe._dict, agreement) -> tuple[bool, str]:
	"""Whether the row meets its origin criterion, and why."""
	criterion = row.origin_criterion
	if not criterion:
		return False, _("Pick the origin criterion.")
	if criterion == "PSR":
		return bool(row.qualifies), _("Product-specific rule: check it against the agreement's annex.")
	if not materials.has_bom and not row.manual_values and criterion != "WO":
		return False, _(
			"Enter the value of non-originating materials (from the manufacturer's cost details for goods you did not make) and tick Values Entered Manually."
		)

	if criterion == "WO":
		if materials.materials:
			return False, _("Wholly obtained goods cannot use non-originating materials.")
		return True, _("No non-originating materials.")

	tests = []
	if "RVC" in criterion:
		tests.append(check_rvc(row, agreement))
	shift = next((rule for rule in TARIFF_SHIFT if rule in criterion.split()), None)
	if shift:
		tests.append(check_tariff_shift(row, materials, shift))

	passed = [ok for ok, _note in tests]
	ok = any(passed) if " or " in criterion else all(passed)
	return ok, " ".join(note for _ok, note in tests)


def check_rvc(row, agreement) -> tuple[bool, str]:
	minimum = flt(agreement.rvc_percent)
	if not minimum:
		return False, _("Set the Minimum RVC % on {0}.").format(agreement.name)
	if flt(row.rvc_percent) >= minimum:
		return True, _("RVC {0}% meets the minimum of {1}%.").format(flt(row.rvc_percent, 2), minimum)
	return False, _("RVC {0}% is below the minimum of {1}%.").format(flt(row.rvc_percent, 2), minimum)


def check_tariff_shift(row, materials: frappe._dict, rule: str) -> tuple[bool, str]:
	digits = TARIFF_SHIFT[rule]
	product = (row.customs_tariff_item or "")[:digits]
	if len(product) < digits:
		return False, _("{0}: set the product's ITC-HS code.").format(rule)
	failing = [
		material.item_code
		for material in materials.materials
		if not material.tariff or material.tariff[:digits] == product
	]
	if failing:
		return False, _(
			"{0} not met: {1} have no ITC-HS code or share the product's {2}-digit code {3}."
		).format(rule, ", ".join(failing), digits, product)
	return True, _("{0} met: every non-originating material is outside {1}.").format(rule, product)
