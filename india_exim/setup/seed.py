"""Standard master data shipped with India EXIM. Existing records are never overwritten."""

import json
from pathlib import Path

import frappe

DATA_DIR = Path(__file__).parent / "data"


def seed_master_data():
	seed_trade_document_types()
	seed_country_groups()


def load(filename: str) -> list[dict]:
	return json.loads((DATA_DIR / filename).read_text())


def seed_trade_document_types():
	for row in load("trade_document_types.json"):
		if frappe.db.exists("Trade Document Type", row["document_name"]):
			continue
		frappe.get_doc({"doctype": "Trade Document Type", **row}).insert(ignore_permissions=True)


def seed_country_groups():
	known_countries = set(frappe.get_all("Country", pluck="name"))
	for row in load("country_groups.json"):
		if frappe.db.exists("Country Group", row["group_name"]):
			continue
		countries = [{"country": country} for country in row["countries"] if country in known_countries]
		frappe.get_doc(
			{
				"doctype": "Country Group",
				"group_name": row["group_name"],
				"description": row["description"],
				"countries": countries,
			}
		).insert(ignore_permissions=True)
