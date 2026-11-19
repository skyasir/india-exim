# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from india_exim.utils.validation import validate_no_overlap, validate_period


class ExportIncentiveRate(Document):
	def validate(self):
		validate_period(self.effective_from, self.effective_to)
		if flt(self.rate) < 0 or flt(self.cap_per_unit) < 0:
			frappe.throw(_("Rate and cap cannot be negative."))

		others = frappe.get_all(
			"Export Incentive Rate",
			filters={
				"scheme": self.scheme,
				"customs_tariff_item": self.customs_tariff_item,
				"name": ("!=", self.name),
			},
			fields=["effective_from", "effective_to"],
		)
		periods = [(row.effective_from, row.effective_to) for row in others]
		periods.append((self.effective_from, self.effective_to))
		validate_no_overlap(periods, _("{0} rate for {1}").format(self.scheme, self.customs_tariff_item))
