"""Value of non-originating materials in an exported product, for its regional value content (RVC).

Taken from the product's default BOM: a material is non-originating when its Country of Origin (Item)
is set and is not India. A material with no Country of Origin is taken as Indian and named in the note,
so it can be checked. Materials from the partner country may count as originating under the agreement;
the values are then corrected on the certificate.
"""

import frappe
from frappe import _
from frappe.utils import flt


def get_non_originating_materials(row, company: str | None) -> frappe._dict:
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
		country = frappe.db.get_value("Item", material.item_code, "country_of_origin")
		if not country:
			assumed.append(material.item_code)
			continue
		if country == "India":
			continue
		value = flt(flt(material.amount) * units, 2)
		result.value += value
		result.materials.append(frappe._dict(item_code=material.item_code, country=country, value=value))

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
