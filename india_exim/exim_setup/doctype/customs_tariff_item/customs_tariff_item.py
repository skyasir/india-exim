# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from india_exim.utils.validation import validate_no_overlap, validate_period


class CustomsTariffItem(Document):
	def validate(self):
		self.tariff_code = (self.tariff_code or "").replace(" ", "").replace(".", "")
		if not (self.tariff_code.isdigit() and len(self.tariff_code) == 8):
			frappe.throw(_("Tariff Code must be an 8-digit ITC-HS code."))

		self.chapter = self.tariff_code[:2]
		if not self.gst_hsn_code and frappe.db.exists("GST HSN Code", self.tariff_code):
			self.gst_hsn_code = self.tariff_code
		for row in self.rates:
			validate_period(row.effective_from, row.effective_to, _("Row {0}").format(row.idx))
		validate_no_overlap(
			[(row.effective_from, row.effective_to) for row in self.rates], _("Customs duty rates")
		)
		self.rates.sort(key=lambda row: row.effective_from)
		for index, row in enumerate(self.rates, start=1):
			row.idx = index
