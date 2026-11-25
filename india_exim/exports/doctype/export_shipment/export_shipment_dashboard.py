from frappe import _


def get_data():
	return {
		"fieldname": "export_shipment",
		"internal_links": {"Sales Invoice": ["invoices", "sales_invoice"]},
		"transactions": [
			{"label": _("Invoices"), "items": ["Sales Invoice"]},
			{"label": _("Customs"), "items": ["Shipping Bill"]},
		],
	}
