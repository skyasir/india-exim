"""Keep India EXIM's fields in their own order on doctypes a site has arranged in Customize Form."""

import json

import frappe


def refresh_field_order(doctypes=None) -> None:
	"""Customize Form saves the whole field order of a doctype, which then wins over insert_after.
	Put India EXIM's fields back where their definition says; every other field stays."""
	from india_exim.setup.custom_fields import CUSTOM_FIELDS

	for doctype in doctypes or CUSTOM_FIELDS:
		fields = CUSTOM_FIELDS[doctype]
		setter = frappe.db.get_value(
			"Property Setter",
			{"doc_type": doctype, "property": "field_order", "doctype_or_field": "DocType"},
			["name", "value"],
			as_dict=True,
		)
		if not setter or not setter.value:
			continue
		order = merge_order(json.loads(setter.value), fields)
		frappe.db.set_value("Property Setter", setter.name, "value", json.dumps(order))
		frappe.clear_cache(doctype=doctype)


def merge_order(order: list[str], fields: list[dict]) -> list[str]:
	ours = {field["fieldname"] for field in fields}
	order = [name for name in order if name not in ours and not name.startswith("exim_")]
	for field in fields:
		after = field.get("insert_after")
		position = order.index(after) + 1 if after in order else len(order)
		order.insert(position, field["fieldname"])
	return order
