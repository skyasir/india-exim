"""Shipment tracking is now a switch, off for new sites. Sites already using it keep it."""

import frappe


def execute():
	if frappe.db.exists("Export Shipment", {}):
		frappe.db.set_single_value("India EXIM Settings", "track_shipments", 1)
