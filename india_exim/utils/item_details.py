"""What the Item master's Export & Import tab gives the trade documents."""

import math

import frappe
from frappe.utils import flt

ITEM_FIELDS = (
	"stock_uom",
	"weight_per_unit",
	"weight_uom",
	"exim_customs_tariff_item",
	"exim_customs_description",
	"exim_uqc",
	"exim_uqc_conversion_factor",
	"exim_gross_weight_per_unit",
	"exim_units_per_package",
	"exim_package_type",
	"exim_package_volume",
	"exim_is_dangerous_goods",
	"exim_un_number",
	"exim_imdg_class",
	"exim_is_reefer",
	"exim_temperature_setting",
	"exim_claim_drawback",
	"exim_drawback_serial_no",
	"exim_claim_rodtep",
	"exim_claim_rosctl",
)


def get_item_details(item_code: str | None) -> frappe._dict:
	if not item_code:
		return frappe._dict()
	return frappe.db.get_value("Item", item_code, ITEM_FIELDS, as_dict=True) or frappe._dict()


def get_uqc(item_code: str | None, stock_qty: float) -> tuple[str | None, float]:
	"""The customs unit and the quantity in it. Without a conversion factor the quantity is
	left as it is (the UQC is then the stock unit)."""
	item = get_item_details(item_code)
	factor = flt(item.exim_uqc_conversion_factor)
	if item.exim_uqc and factor:
		return item.exim_uqc, flt(stock_qty) * factor
	return item.exim_uqc or item.stock_uom, flt(stock_qty)


def get_packing(item_code: str | None, stock_qty: float) -> frappe._dict:
	"""Net and gross weight (kg) and packages for a quantity, from the item's packing details."""
	item = get_item_details(item_code)
	per_package = flt(item.exim_units_per_package)
	packages = math.ceil(flt(stock_qty) / per_package) if per_package else 0
	to_kg = get_kg_factor(item.weight_uom)
	return frappe._dict(
		net_weight=flt(item.weight_per_unit) * flt(stock_qty) * to_kg,
		gross_weight=flt(item.exim_gross_weight_per_unit or item.weight_per_unit) * flt(stock_qty) * to_kg,
		packages=packages,
		package_type=item.exim_package_type,
		volume=flt(item.exim_package_volume) * packages,
	)


def get_kg_factor(weight_uom: str | None) -> float:
	"""Shipping documents state weights in kg; convert from the item's Weight UOM."""
	if not weight_uom or weight_uom == "Kg":
		return 1.0
	from erpnext.stock.doctype.item.item import get_uom_conv_factor

	return flt(get_uom_conv_factor(weight_uom, "Kg")) or 1.0


WEIGHT_UOMS = ("Kg", "Gram", "Tonne")


def get_quantity_in(
	item_code: str | None, uom: str | None, stock_qty: float, uqc: str | None, uqc_qty: float
) -> float | None:
	"""A quantity in the unit a schedule states its cap in, or None when it cannot be worked out."""
	if not uom or uom == uqc:
		return flt(uqc_qty)
	item = get_item_details(item_code)
	if uom == item.stock_uom:
		return flt(stock_qty)
	if uom in WEIGHT_UOMS and flt(item.weight_per_unit):
		kg = get_packing(item_code, stock_qty).net_weight
		return kg / {"Kg": 1, "Gram": 0.001, "Tonne": 1000}[uom]
	factor = frappe.db.get_value(
		"UOM Conversion Detail", {"parent": item_code, "parenttype": "Item", "uom": uom}, "conversion_factor"
	)
	if flt(factor):
		return flt(stock_qty) / flt(factor)
	from erpnext.stock.doctype.item.item import get_uom_conv_factor

	for source, qty in ((item.stock_uom, stock_qty), (uqc, uqc_qty)):
		if source and flt(get_uom_conv_factor(source, uom)):
			return flt(qty) * flt(get_uom_conv_factor(source, uom))
	return None
