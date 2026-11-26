# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

import re

import frappe
from frappe import _
from frappe.model.document import Document

# last character of an Indian customs port code
INDIAN_PORT_TYPES = {
	"1": "Sea",
	"2": "Rail",
	"4": "Air",
	"5": "Foreign Post Office",
	"6": "ICD / CFS / SEZ",
	"B": "Land Border",
}


class PortMaster(Document):
	def before_naming(self):
		self.port_code = normalise_code(self.port_code)

	def validate(self):
		self.port_code = normalise_code(self.port_code)
		self.port_name = (self.port_name or "").strip() or self.port_code
		self.set_country()
		if not self.port_type and self.port_country == "India":
			self.port_type = INDIAN_PORT_TYPES.get(self.port_code[-1:])
		self.validate_ad_codes()

	def set_country(self):
		"""Frappe fills a Country field with the user's country (India), so a port abroad would be
		saved as Indian. Indian customs port codes all start with IN; any other code is abroad."""
		if self.port_country == "India" and not self.port_code.startswith("IN"):
			self.port_country = None
		self.port_country = self.port_country or get_country_from_code(self.port_code)
		if not self.port_country:
			frappe.throw(_("Set the country of port {0}.").format(frappe.bold(self.port_code)))

	def validate_ad_codes(self):
		if self.ad_codes and self.port_country != "India":
			frappe.throw(_("AD codes are registered only at Indian ports."))

		seen, defaults = set(), set()
		for row in self.ad_codes:
			row.ad_code = (row.ad_code or "").strip()
			if (row.company, row.ad_code) in seen:
				frappe.throw(
					_("Row {0}: AD code {1} is entered twice.").format(row.idx, frappe.bold(row.ad_code))
				)
			seen.add((row.company, row.ad_code))
			if row.is_default:
				if row.company in defaults:
					frappe.throw(
						_("Row {0}: {1} already has a default AD code at this port.").format(
							row.idx, row.company
						)
					)
				defaults.add(row.company)


def normalise_code(code: str | None) -> str:
	return (code or "").strip().upper()


def get_country_from_code(code: str) -> str | None:
	"""A UN/LOCODE starts with the country's ISO code: AEJEA is in the United Arab Emirates."""
	if not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{3,4}", code):
		return None
	return frappe.db.get_value("Country", {"code": code[:2].lower()})


def get_port_name(code: str | None) -> str:
	return (code and frappe.db.get_value("Port Master", code, "port_name")) or ""


def get_indian_port(code: str | None) -> str | None:
	"""The Port Master of an Indian customs port code, as it is spelt there."""
	return frappe.db.get_value("Port Master", {"name": code, "port_country": "India"}) if code else None


def is_indian_port(code: str | None) -> bool:
	return bool(get_indian_port(code))


def get_ad_codes(company: str, port_code: str | None = None, fields=("ad_code",)) -> list[frappe._dict]:
	"""The company's AD codes at enabled ports, the default first."""
	filters = {"parenttype": "Port Master", "company": company}
	if port_code:
		filters["parent"] = port_code
	enabled = set(frappe.get_all("Port Master", {"disabled": 0, "port_country": "India"}, pluck="name"))
	rows = frappe.get_all(
		"Port AD Code",
		filters=filters,
		fields=["parent", *fields],
		order_by="is_default desc, idx asc",
	)
	return [row for row in rows if row.parent in enabled]


def get_only_port(company: str) -> str | None:
	"""The port, when the company has AD codes at just one."""
	ports = {row.parent for row in get_ad_codes(company)}
	return ports.pop() if len(ports) == 1 else None


def get_ad_code(company: str, port_code: str) -> str | None:
	rows = get_ad_codes(company, port_code)
	return rows[0].ad_code if rows else None


def seed_ports():
	seed_indian_ports()
	seed_ports_abroad()


def seed_ports_abroad():
	"""The main ports India trades through, with their UN/LOCODEs. Others are added when first used."""
	from india_exim.setup.seed import load

	for row in load("ports_abroad.json"):
		if frappe.db.exists("Port Master", row["port_code"]):
			continue
		port = frappe.get_doc({"doctype": "Port Master", **row})
		if port.port_country or get_country_from_code(port.port_code):
			port.insert(ignore_permissions=True)


def seed_indian_ports():
	"""India Compliance's customs port codes as ports. Ports already there, edited or not, are kept."""
	from india_compliance.gst_india.constants import PORT_CODES

	existing = {name.upper() for name in frappe.get_all("Port Master", pluck="name")}
	missing = [code for code in PORT_CODES if code not in existing]
	if not missing:
		return

	now = frappe.utils.now()
	user = frappe.session.user
	frappe.db.bulk_insert(
		"Port Master",
		[
			"name",
			"port_code",
			"port_name",
			"port_country",
			"port_type",
			"creation",
			"modified",
			"owner",
			"modified_by",
		],
		[
			(code, code, PORT_CODES[code], "India", INDIAN_PORT_TYPES.get(code[-1]), now, now, user, user)
			for code in missing
		],
	)
