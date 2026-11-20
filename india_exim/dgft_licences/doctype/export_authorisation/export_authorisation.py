# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, today

from india_exim.dgft_licences.authorisation import compute_position, default_dates


class ExportAuthorisation(Document):
	def validate(self):
		self.authorisation_number = (self.authorisation_number or "").strip().upper()
		default_dates(self)
		if getdate(self.eo_period_upto) < getdate(self.authorisation_date):
			frappe.throw(_("The export obligation period cannot end before the authorisation date."))
		self.validate_rows()
		# rows may have been added for items already imported or exported under this licence
		compute_position(self)
		self.set_status()

	def validate_rows(self):
		for table in ("imports", "exports"):
			seen = set()
			for row in self.get(table):
				key = (row.customs_tariff_item, row.item_code or "")
				if key in seen:
					frappe.throw(
						_("{0} row {1}: {2} is listed twice.").format(
							_(table.title()), row.idx, row.item_code or row.customs_tariff_item
						)
					)
				seen.add(key)

	def set_totals(self, extra_cif=0.0, extra_duty=0.0, extra_fob=0.0):
		self.total_cif_allowed = sum(flt(row.cif_allowed) for row in self.imports)
		self.total_cif_imported = sum(flt(row.cif_imported) for row in self.imports) + flt(extra_cif)
		self.total_duty_saved = sum(flt(row.duty_saved) for row in self.imports) + flt(extra_duty)
		if self.scheme == "EPCG":
			self.eo_required = flt(self.total_duty_saved * flt(self.eo_multiple or 6), 2)
		else:
			self.eo_required = sum(flt(row.fob_required) for row in self.exports)
		self.eo_fulfilled = sum(flt(row.fob_exported) for row in self.exports) + flt(extra_fob)
		self.eo_balance = max(flt(self.eo_required) - flt(self.eo_fulfilled), 0)
		self.eo_percent = (
			min(flt(self.eo_fulfilled) * 100 / flt(self.eo_required), 100) if flt(self.eo_required) else 0
		)

	def is_obligation_met(self) -> bool:
		if not flt(self.eo_required) or flt(self.eo_fulfilled) < flt(self.eo_required) - 0.5:
			return False
		if self.scheme == "Advance Authorisation":
			# the quantities in the authorisation must be exported as well as the value
			return all(
				flt(row.qty_exported) >= flt(row.qty_required) - 0.0001
				for row in self.exports
				if flt(row.qty_required)
			)
		return True

	def set_status(self):
		if self.is_cancelled:
			status = "Cancelled"
		elif self.eodc_date or self.eodc_number:
			status = "Redeemed"
		elif self.regularisation_reference:
			status = "Regularised"
		elif self.is_obligation_met():
			status = "EO Fulfilled"
		elif self.eo_period_upto and getdate(self.eo_period_upto) < getdate(today()):
			status = "EO Period Over"
		else:
			status = "Active"
		self.status = status
