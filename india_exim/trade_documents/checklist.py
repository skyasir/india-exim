"""Builds a shipment's document checklist from Document Requirement Templates.

Rules are merged from least to most specific: the Indian statutory set first, then rules with
more matching conditions. When two rules ask for the same document, the stricter one wins
(mandatory beats optional, the earlier due date wins) and their instructions are combined.
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, getdate

DONE_STATUSES = ("Received", "Checked", "Sent", "Accepted", "Not Required")
CONDITION_FIELDS = (
	"country",
	"country_group",
	"tariff_prefixes",
	"item_group",
	"incoterm",
	"payment_terms_type",
	"mode_of_transport",
	"customer",
	"supplier",
)


class ShipmentContext(frappe._dict):
	"""What a rule is matched against: country, party, terms, tariffs and item groups."""


def is_within_group(item_group: str, rule_group: str) -> bool:
	"""True when item_group is rule_group or one of its descendants."""
	if item_group == rule_group:
		return True
	bounds = frappe.get_cached_value("Item Group", rule_group, ["lft", "rgt"])
	child = frappe.get_cached_value("Item Group", item_group, ["lft", "rgt"])
	return bool(bounds and child and bounds[0] < child[0] and child[1] < bounds[1])


def get_context(shipment) -> ShipmentContext:
	tariffs, item_groups = set(), set()
	for item_code in get_item_codes(shipment):
		tariff, item_group = frappe.db.get_value(
			"Item", item_code, ["exim_customs_tariff_item", "item_group"]
		)
		if tariff:
			tariffs.add(tariff)
		if item_group:
			item_groups.add(item_group)

	return ShipmentContext(
		direction="Export" if shipment.doctype == "Export Shipment" else "Import",
		country=shipment.get("destination_country") or shipment.get("origin_country"),
		customer=shipment.get("customer"),
		supplier=shipment.get("supplier"),
		incoterm=shipment.get("incoterm"),
		payment_terms_type=shipment.get("payment_terms_type"),
		mode_of_transport=shipment.get("mode_of_transport"),
		tariffs=tariffs,
		item_groups=item_groups,
		groups_of_country=get_country_groups(
			shipment.get("destination_country") or shipment.get("origin_country")
		),
	)


def get_item_codes(shipment) -> set[str]:
	child_doctype, invoice_field = (
		("Sales Invoice Item", "sales_invoice")
		if shipment.doctype == "Export Shipment"
		else ("Purchase Invoice Item", "purchase_invoice")
	)
	invoices = [row.get(invoice_field) for row in shipment.get("invoices") or [] if row.get(invoice_field)]
	if not invoices:
		return set()
	return set(frappe.get_all(child_doctype, filters={"parent": ("in", invoices)}, pluck="item_code"))


def get_country_groups(country: str | None) -> set[str]:
	if not country:
		return set()
	return set(
		frappe.get_all(
			"Country Group Member",
			filters={"country": country, "parenttype": "Country Group"},
			pluck="parent",
		)
	)


def matches(template, context: ShipmentContext) -> bool:
	if template.is_statutory:
		return True
	checks = {
		"country": lambda value: value == context.country,
		"country_group": lambda value: value in context.groups_of_country,
		"tariff_prefixes": lambda value: any(
			tariff.startswith(prefix.strip())
			for prefix in value.split(",")
			if prefix.strip()
			for tariff in context.tariffs
		),
		"item_group": lambda value: any(is_within_group(group, value) for group in context.item_groups),
		"incoterm": lambda value: value == context.incoterm,
		"payment_terms_type": lambda value: value == context.payment_terms_type,
		"mode_of_transport": lambda value: value == context.mode_of_transport,
		"customer": lambda value: value == context.customer,
		"supplier": lambda value: value == context.supplier,
	}
	return all(checks[field](template.get(field)) for field in CONDITION_FIELDS if template.get(field))


def specificity(template) -> int:
	if template.is_statutory:
		return -1
	return sum(1 for field in CONDITION_FIELDS if template.get(field))


def get_matching_templates(context: ShipmentContext) -> list:
	names = frappe.get_all(
		"Document Requirement Template", filters={"enabled": 1, "direction": context.direction}, pluck="name"
	)
	templates = [frappe.get_cached_doc("Document Requirement Template", name) for name in names]
	matched = [template for template in templates if matches(template, context)]
	return sorted(matched, key=lambda template: (specificity(template), template.name))


def merge_requirements(templates: list) -> dict[str, frappe._dict]:
	merged: dict[str, frappe._dict] = {}
	for template in templates:
		for requirement in template.requirements:
			current = merged.get(requirement.document_type)
			incoming = frappe._dict(
				document_type=requirement.document_type,
				mandatory=cint(requirement.mandatory),
				stage=requirement.stage,
				due_event=requirement.due_event,
				due_offset_days=cint(requirement.due_offset_days),
				responsible=requirement.responsible,
				instructions=requirement.instructions or "",
				source=template.name,
			)
			merged[requirement.document_type] = combine(current, incoming) if current else incoming
	return merged


def combine(current: frappe._dict, incoming: frappe._dict) -> frappe._dict:
	"""The more specific rule (incoming) leads; the stricter value wins."""
	combined = frappe._dict(incoming)
	combined.mandatory = max(current.mandatory, incoming.mandatory)
	if not incoming.due_event:
		combined.due_event, combined.due_offset_days = current.due_event, current.due_offset_days
	elif incoming.due_event == current.due_event:
		combined.due_offset_days = min(current.due_offset_days, incoming.due_offset_days)
	combined.responsible = incoming.responsible or current.responsible
	combined.instructions = "\n".join(text for text in (current.instructions, incoming.instructions) if text)
	combined.source = f"{current.source}, {incoming.source}"
	return combined


def get_event_dates(shipment) -> dict:
	return {
		"Order Date": getdate(shipment.creation) if shipment.get("creation") else getdate(),
		"ETD": shipment.get("etd"),
		"BL Date": shipment.get("bl_date"),
		"ETA": shipment.get("eta"),
	}


def get_due_date(row, event_dates: dict):
	event_date = event_dates.get(row.get("due_event")) if row.get("due_event") else None
	return add_days(event_date, cint(row.get("due_offset_days"))) if event_date else None


def apply_checklist(shipment) -> int:
	"""Add or refresh rule-based rows on the shipment. Returns the number of rows added."""
	required = merge_requirements(get_matching_templates(get_context(shipment)))
	existing = {row.document_type: row for row in shipment.documents}
	added = 0

	for row in list(shipment.documents):
		if row.source and row.document_type not in required and row.status == "Pending":
			shipment.remove(row)

	for document_type, requirement in required.items():
		row = existing.get(document_type)
		if not row:
			row = shipment.append("documents", {"document_type": document_type, "status": "Pending"})
			added += 1
		document = frappe.get_cached_value(
			"Trade Document Type", document_type, ["issued_by", "originals", "instructions"], as_dict=True
		)
		row.mandatory = max(cint(row.mandatory), requirement.mandatory)
		row.stage = requirement.stage
		row.due_event = requirement.due_event
		row.due_offset_days = requirement.due_offset_days
		row.responsible = row.responsible or requirement.responsible
		row.issued_by = document.issued_by
		row.originals_required = document.originals
		row.instructions = requirement.instructions or frappe.utils.strip_html(document.instructions or "")
		row.source = requirement.source

	refresh_due_dates(shipment)
	return added


def refresh_due_dates(shipment) -> None:
	event_dates = get_event_dates(shipment)
	for row in shipment.documents:
		if row.due_event:
			row.due_date = get_due_date(row, event_dates)


def get_readiness(shipment) -> float:
	rows = [row for row in shipment.documents if row.mandatory] or list(shipment.documents)
	if not rows:
		return 0.0
	done = sum(1 for row in rows if row.status in DONE_STATUSES)
	return round(done * 100 / len(rows), 1)


def get_pending_mandatory(shipment) -> list[str]:
	return [
		row.document_type for row in shipment.documents if row.mandatory and row.status not in DONE_STATUSES
	]


def enforce_gate(shipment, action_label: str) -> None:
	pending = get_pending_mandatory(shipment)
	if not pending:
		return
	mode = frappe.db.get_single_value("India EXIM Settings", "checklist_gate") or "Warn"
	if mode == "Off":
		return
	message = _("{0} with mandatory documents still pending: {1}").format(
		action_label, ", ".join(frappe.bold(name) for name in pending)
	)
	if mode == "Block":
		frappe.throw(message, title=_("Documents Pending"))
	frappe.msgprint(message, title=_("Documents Pending"), indicator="orange")
