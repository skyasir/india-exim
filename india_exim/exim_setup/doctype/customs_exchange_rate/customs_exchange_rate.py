# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class CustomsExchangeRate(Document):
	def validate(self):
		if self.currency == "INR":
			frappe.throw(_("Customs exchange rates are only needed for foreign currencies."))
		if self.export_rate <= 0 or self.import_rate <= 0:
			frappe.throw(_("Export and import rates must be greater than zero."))
