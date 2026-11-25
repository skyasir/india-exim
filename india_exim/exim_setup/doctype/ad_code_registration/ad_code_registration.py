# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from india_compliance.gst_india.constants import PORT_CODES


class ADCodeRegistration(Document):
	def validate(self):
		self.port_code = (self.port_code or "").strip().upper()
		if self.port_code not in PORT_CODES:
			frappe.throw(
				_("{0} is not a valid Indian customs port code.").format(frappe.bold(self.port_code))
			)
		self.port_name = PORT_CODES[self.port_code]

		if self.is_default:
			frappe.db.set_value(
				"AD Code Registration",
				{"company": self.company, "port_code": self.port_code, "name": ("!=", self.name)},
				"is_default",
				0,
			)


def get_only_port(company: str) -> str | None:
	"""The port, when the company has AD codes at just one."""
	ports = set(
		frappe.get_all("AD Code Registration", filters={"company": company, "disabled": 0}, pluck="port_code")
	)
	return ports.pop() if len(ports) == 1 else None


def get_ad_code(company: str, port_code: str) -> str | None:
	filters = {"company": company, "port_code": port_code, "disabled": 0}
	return frappe.db.get_value(
		"AD Code Registration", {**filters, "is_default": 1}, "ad_code"
	) or frappe.db.get_value("AD Code Registration", filters, "ad_code")
