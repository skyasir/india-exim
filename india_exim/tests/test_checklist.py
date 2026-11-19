import frappe
from frappe.tests import IntegrationTestCase, change_settings
from frappe.utils import add_days, getdate

from india_exim.tests.fixtures import COMPANY, FOREIGN_CUSTOMER
from india_exim.trade_documents.checklist import get_pending_mandatory, get_readiness


def make_template(name, requirements, **conditions):
	if frappe.db.exists("Document Requirement Template", name):
		frappe.delete_doc("Document Requirement Template", name, force=True)
	return frappe.get_doc(
		{
			"doctype": "Document Requirement Template",
			"template_name": name,
			"direction": "Export",
			"requirements": requirements,
			**conditions,
		}
	).insert()


class TestDocumentChecklist(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.db.delete("Document Requirement Template")
		make_template(
			"Test India Statutory",
			[
				{"document_type": "Commercial Invoice", "mandatory": 1, "stage": "At Shipment"},
				{"document_type": "Packing List", "mandatory": 1, "stage": "At Shipment"},
			],
			is_statutory=1,
		)
		make_template(
			"Test United States",
			[
				{
					"document_type": "Commercial Invoice",
					"mandatory": 1,
					"due_event": "ETD",
					"due_offset_days": -2,
				},
				{
					"document_type": "FDA Prior Notice Confirmation",
					"mandatory": 0,
					"instructions": "Food only",
				},
			],
			for_country="United States",
		)
		make_template(
			"Test Buyer Rule",
			[
				{
					"document_type": "FDA Prior Notice Confirmation",
					"mandatory": 1,
					"instructions": "Buyer insists",
				},
				{
					"document_type": "Commercial Invoice",
					"mandatory": 1,
					"due_event": "ETD",
					"due_offset_days": -5,
				},
			],
			for_country="United States",
			for_customer=FOREIGN_CUSTOMER,
		)
		make_template(
			"Test Saudi Only",
			[{"document_type": "Product Conformity Certificate (SABER / SASO)", "mandatory": 1}],
			for_country="Saudi Arabia",
		)

	def make_shipment(self, **values):
		return frappe.get_doc(
			{
				"doctype": "Export Shipment",
				"company": COMPANY,
				"customer": FOREIGN_CUSTOMER,
				"destination_country": "United States",
				"etd": add_days(getdate(), 20),
				**values,
			}
		).insert()

	def test_rules_merge_with_stricter_requirement_winning(self):
		shipment = self.make_shipment()
		rows = {row.document_type: row for row in shipment.documents}

		self.assertEqual(set(rows), {"Commercial Invoice", "Packing List", "FDA Prior Notice Confirmation"})
		self.assertNotIn("Product Conformity Certificate (SABER / SASO)", rows)

		fda = rows["FDA Prior Notice Confirmation"]
		self.assertEqual(fda.mandatory, 1)
		self.assertIn("Food only", fda.instructions)
		self.assertIn("Buyer insists", fda.instructions)
		self.assertEqual(fda.source, "Test United States, Test Buyer Rule")

		invoice = rows["Commercial Invoice"]
		self.assertEqual(getdate(invoice.due_date), add_days(shipment.etd, -5))

	def test_due_dates_follow_etd_changes(self):
		shipment = self.make_shipment()
		shipment.etd = add_days(getdate(), 40)
		shipment.save()
		invoice = next(row for row in shipment.documents if row.document_type == "Commercial Invoice")
		self.assertEqual(getdate(invoice.due_date), add_days(getdate(), 35))

	def test_readiness_counts_mandatory_documents(self):
		shipment = self.make_shipment()
		self.assertEqual(shipment.readiness_percent, 0)
		for row in shipment.documents:
			if row.document_type == "Commercial Invoice":
				row.status = "Received"
		shipment.save()
		self.assertAlmostEqual(get_readiness(shipment), 33.3, places=1)
		self.assertEqual(len(get_pending_mandatory(shipment)), 2)

	@change_settings("India EXIM Settings", {"checklist_gate": "Block"})
	def test_gate_blocks_documents_sent_with_pending_mandatory(self):
		shipment = self.make_shipment()
		shipment.status = "Documents Sent"
		self.assertRaises(frappe.ValidationError, shipment.save)

		shipment.reload()
		for row in shipment.documents:
			row.status = "Sent"
		shipment.status = "Documents Sent"
		shipment.save()
		self.assertEqual(shipment.readiness_percent, 100)

	def test_statutory_template_ignores_conditions(self):
		template = make_template(
			"Test Statutory With Country",
			[{"document_type": "Shipping Bill", "mandatory": 1}],
			is_statutory=1,
			for_country="Saudi Arabia",
		)
		self.assertIsNone(template.for_country)
		frappe.delete_doc("Document Requirement Template", template.name)

	def test_new_rule_is_not_narrowed_by_global_defaults(self):
		"""System defaults such as country = India must not leak into rule conditions."""
		frappe.db.set_default("country", "India")
		template = make_template(
			"Test Group Only",
			[{"document_type": "Shipping Bill", "mandatory": 1}],
			for_country_group="GCC",
		)
		self.assertIsNone(template.for_country)
		self.assertIsNone(template.for_item_group)
		frappe.delete_doc("Document Requirement Template", template.name)
