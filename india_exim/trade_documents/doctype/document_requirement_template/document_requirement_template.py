# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from india_exim.trade_documents.checklist import CONDITION_FIELDS


class DocumentRequirementTemplate(Document):
	def validate(self):
		if self.is_statutory:
			for field in CONDITION_FIELDS:
				self.set(field, None)
		if self.item_group and not frappe.db.get_value("Item Group", self.item_group, "parent_item_group"):
			# the root group means "any item"; a default must not narrow the rule
			self.item_group = None
		if self.direction == "Export":
			self.supplier = None
		else:
			self.customer = None

		seen = set()
		for row in self.requirements:
			if row.document_type in seen:
				frappe.throw(
					_("Row {0}: {1} is listed twice.").format(row.idx, frappe.bold(row.document_type))
				)
			seen.add(row.document_type)

		if self.tariff_prefixes:
			prefixes = [prefix.strip() for prefix in self.tariff_prefixes.split(",") if prefix.strip()]
			if not all(prefix.isdigit() for prefix in prefixes):
				frappe.throw(_("Tariff prefixes must be digits, e.g. 09, 1006, 52."))
			self.tariff_prefixes = ", ".join(prefixes)
