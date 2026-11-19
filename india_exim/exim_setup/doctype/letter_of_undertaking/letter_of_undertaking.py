# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class LetterofUndertaking(Document):
	def before_validate(self):
		if self.fiscal_year and not (self.valid_from and self.valid_upto):
			start, end = frappe.db.get_value(
				"Fiscal Year", self.fiscal_year, ["year_start_date", "year_end_date"]
			)
			self.valid_from = self.valid_from or start
			self.valid_upto = self.valid_upto or end

	def validate(self):
		if getdate(self.valid_upto) < getdate(self.valid_from):
			frappe.throw(_("Valid Upto cannot be before Valid From."))

		overlapping = frappe.db.get_value(
			"Letter of Undertaking",
			{
				"company": self.company,
				"name": ("!=", self.name),
				"valid_from": ("<=", self.valid_upto),
				"valid_upto": (">=", self.valid_from),
			},
		)
		if overlapping:
			frappe.throw(_("Validity overlaps with {0}.").format(frappe.bold(overlapping)))
