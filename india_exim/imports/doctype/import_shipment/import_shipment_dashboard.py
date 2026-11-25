from frappe import _


def get_data():
	return {
		"fieldname": "exim_import_shipment",
		"internal_links": {
			"Purchase Order": ["orders", "purchase_order"],
			"Purchase Invoice": ["invoices", "purchase_invoice"],
		},
		"transactions": [{"label": _("Purchase"), "items": ["Purchase Order", "Purchase Invoice"]}],
	}
