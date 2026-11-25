"""Connections added to ERPNext's documents."""

from frappe import _


def sales_invoice(data):
	data.setdefault("transactions", []).append(
		{"label": _("Export"), "items": ["Export Shipment", "Shipping Bill"]}
	)
	data.setdefault("non_standard_fieldnames", {}).update(
		{"Export Shipment": "sales_invoice", "Shipping Bill": "sales_invoice"}
	)
	return data


def purchase_order(data):
	data.setdefault("transactions", []).append({"label": _("Import"), "items": ["Import Shipment"]})
	data.setdefault("non_standard_fieldnames", {})["Import Shipment"] = "purchase_order"
	return data


def purchase_invoice(data):
	data.setdefault("transactions", []).append({"label": _("Import"), "items": ["Import Shipment"]})
	data.setdefault("non_standard_fieldnames", {})["Import Shipment"] = "purchase_invoice"
	return data
