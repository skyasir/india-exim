# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, flt, getdate

from india_exim.utils.validation import validate_no_overlap, validate_period


class ExportIncentiveRate(Document):
	def validate(self):
		validate_period(self.effective_from, self.effective_to)
		if min(flt(self.rate), flt(self.amount_per_unit), flt(self.cap_per_unit)) < 0:
			frappe.throw(_("Rate, fixed amount and cap cannot be negative."))
		if flt(self.rate) and flt(self.amount_per_unit):
			frappe.throw(_("Enter either a Rate % of FOB or a Fixed Amount Per Unit, not both."))
		if not self.customs_tariff_item and (self.scheme == "RoDTEP" or not self.schedule_serial_no):
			frappe.throw(
				_("Enter the Tariff Item, or the Schedule Serial No. of a drawback or RoSCTL entry.")
			)
		self.validate_item()
		if self.scheme != "RoSCTL":
			self.central_rate = self.central_cap_per_unit = 0
		elif min(flt(self.central_rate), flt(self.central_cap_per_unit)) < 0:
			frappe.throw(_("Rate, fixed amount and cap cannot be negative."))
		if self.is_new():
			self.close_previous_rate()
		self.warn_if_not_notified()

		others = frappe.get_all(
			"Export Incentive Rate",
			filters={
				"scheme": self.scheme,
				"customs_tariff_item": self.customs_tariff_item or ("is", "not set"),
				"item_code": self.item_code or ("is", "not set"),
				"name": ("!=", self.name),
			},
			fields=["effective_from", "effective_to", "schedule_serial_no"],
		)
		# a schedule can have several entries for one tariff item (e.g. by material), each with
		# its own serial number; only periods of the same entry may not overlap
		periods = [
			(row.effective_from, row.effective_to)
			for row in others
			if (row.schedule_serial_no or "") == (self.schedule_serial_no or "")
		]
		periods.append((self.effective_from, self.effective_to))
		label = _("{0} rate for {1}").format(self.scheme, self.customs_tariff_item or "")
		if self.schedule_serial_no:
			label += " " + _("(Serial No. {0})").format(self.schedule_serial_no)
		validate_no_overlap(periods, label)

	def validate_item(self):
		if self.scheme != "Duty Drawback":
			self.item_code = None  # the other schemes have no product-specific rates
		if not self.item_code:
			return
		tariff = frappe.db.get_value("Item", self.item_code, "exim_customs_tariff_item")
		if tariff != self.customs_tariff_item:
			frappe.throw(
				_("Item {0} has Tariff Item {1}, not {2}.").format(
					self.item_code, tariff or "-", self.customs_tariff_item
				)
			)

	def close_previous_rate(self):
		"""A newer rate for the same entry ends the open-ended one before it, so a new notification
		can be loaded (by hand or with Data Import) without editing the old rate."""
		previous = frappe.get_all(
			"Export Incentive Rate",
			filters={
				"scheme": self.scheme,
				"customs_tariff_item": self.customs_tariff_item or ("is", "not set"),
				"schedule_serial_no": self.schedule_serial_no or ("is", "not set"),
				"item_code": self.item_code or ("is", "not set"),
				"effective_from": ("<", self.effective_from),
				"effective_to": ("is", "not set"),
			},
			pluck="name",
		)
		for name in previous:
			frappe.db.set_value(
				"Export Incentive Rate", name, "effective_to", add_days(getdate(self.effective_from), -1)
			)

	def warn_if_not_notified(self):
		from india_exim.setup.tariff_data import describe, differs_from_notified

		notified = differs_from_notified(self)
		if notified:
			frappe.msgprint(
				_(
					"The notified {0} rate for {1} from {2} is {3} ({4}). This rate is {5}. Use the notified rate unless you have a later notification."
				).format(
					self.scheme,
					frappe.bold(self.customs_tariff_item),
					frappe.format(notified["effective_from"], {"fieldtype": "Date"}),
					describe(notified),
					notified["notification"],
					describe(self),
				),
				title=_("Differs from the Notified Rate"),
				indicator="orange",
			)
