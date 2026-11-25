# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class IndiaEXIMSettings(Document):
	def validate(self):
		self.validate_fema_periods()

	def validate_fema_periods(self):
		seen = set()
		for row in self.fema_periods:
			if (row.months or 0) <= 0:
				frappe.throw(_("Row {0}: Months must be greater than zero.").format(row.idx))
			key = (row.period_for, str(row.effective_from))
			if key in seen:
				frappe.throw(
					_("Row {0}: {1} from {2} is listed twice.").format(
						row.idx, _(row.period_for), frappe.format(row.effective_from, {"fieldtype": "Date"})
					)
				)
			seen.add(key)
		self.fema_periods.sort(key=lambda row: (row.period_for, str(row.effective_from)))
		for index, row in enumerate(self.fema_periods, start=1):
			row.idx = index
