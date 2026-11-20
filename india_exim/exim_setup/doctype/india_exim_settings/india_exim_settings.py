# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class IndiaEXIMSettings(Document):
	def validate(self):
		for fieldname in ("export_realisation_months", "import_payment_months"):
			if (self.get(fieldname) or 0) <= 0:
				frappe.throw(_("{0} must be greater than zero.").format(_(self.meta.get_label(fieldname))))
