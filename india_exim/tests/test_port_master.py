"""Ports are picked from the Port Master; AD codes are registered on the Indian port."""

import frappe
from frappe.tests import IntegrationTestCase

from india_exim.exim_setup.doctype.port_master.port_master import get_ad_code, get_only_port
from india_exim.tests.fixtures import COMPANY, setup_exim_company
from india_exim.utils.jinja import exim_port


class TestPortMaster(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		setup_exim_company()

	def test_ports_are_preloaded(self):
		nhava_sheva = frappe.get_doc("Port Master", "INNSA1")
		self.assertEqual((nhava_sheva.port_country, nhava_sheva.port_type), ("India", "Sea"))
		self.assertEqual(frappe.db.get_value("Port Master", "INDEL4", "port_type"), "Air")
		self.assertEqual(frappe.db.get_value("Port Master", "AEJEA", "port_country"), "United Arab Emirates")
		self.assertEqual(exim_port("AEJEA"), "Jebel Ali (AEJEA)")

	def test_new_port_takes_country_from_its_code(self):
		port = frappe.get_doc(
			{"doctype": "Port Master", "port_code": " nlams ", "port_name": "Amsterdam"}
		).insert()
		self.addCleanup(port.delete)
		self.assertEqual((port.name, port.port_country), ("NLAMS", "Netherlands"))
		# the user's default country, India, does not stick to a port abroad
		port = frappe.get_doc(
			{
				"doctype": "Port Master",
				"port_code": "ESALG",
				"port_name": "Algeciras",
				"port_country": "India",
			}
		).insert()
		self.addCleanup(port.delete)
		self.assertEqual(port.port_country, "Spain")
		self.assertRaises(
			frappe.ValidationError,
			frappe.get_doc({"doctype": "Port Master", "port_code": "PARIS-X", "port_name": "Paris"}).insert,
		)

	def test_ad_codes_on_the_port(self):
		port = frappe.get_doc("Port Master", "INTUT1")
		port.ad_codes = []
		port.append("ad_codes", {"company": COMPANY, "ad_code": "1111111"})
		port.append("ad_codes", {"company": COMPANY, "ad_code": "2222222", "is_default": 1})
		port.save()
		self.addCleanup(lambda: frappe.get_doc("Port Master", "INTUT1").update({"ad_codes": []}).save())
		self.assertEqual(get_ad_code(COMPANY, "INTUT1"), "2222222")

		port.ad_codes[0].is_default = 1
		self.assertRaises(frappe.ValidationError, port.save)

		abroad = frappe.get_doc("Port Master", "SGSIN")
		abroad.append("ad_codes", {"company": COMPANY, "ad_code": "3333333"})
		self.assertRaises(frappe.ValidationError, abroad.save)

		frappe.db.set_value("Port Master", "INTUT1", "disabled", 1)
		self.addCleanup(frappe.db.set_value, "Port Master", "INTUT1", "disabled", 0)
		self.assertIsNone(get_ad_code(COMPANY, "INTUT1"))
		self.assertNotEqual(get_only_port(COMPANY), "INTUT1")
