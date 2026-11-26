"""The Supplier's FTA fields are gone (the trade agreement is claimed on each Bill of Entry). What was
entered is moved to the supplier's details."""

import frappe

from india_exim.patches.v0_2.keep_removed_field_text import get_rows


def execute():
	fields = ["exim_fta_eligible", "exim_trade_agreement", "supplier_details"]
	for row in get_rows("Supplier", fields, ["exim_fta_eligible", "exim_trade_agreement"]):
		note = (
			f"Trade Agreement: {row.exim_trade_agreement}"
			if row.get("exim_trade_agreement")
			else "Supplies eligible for FTA concession"
		)
		text = "\n".join(part for part in (row.get("supplier_details"), note) if part)
		frappe.db.set_value("Supplier", row.name, "supplier_details", text, update_modified=False)
