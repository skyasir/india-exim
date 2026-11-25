from frappe import _


def get_data():
	return {
		"fieldname": "shipping_bill",
		"internal_links": {
			"Sales Invoice": ["items", "sales_invoice"],
			"Export Shipment": "export_shipment",
		},
		"non_standard_fieldnames": {"Journal Entry": "exim_reference_name"},
		"transactions": [
			{"label": _("Export"), "items": ["Sales Invoice", "Export Shipment"]},
			{"label": _("Incentives"), "items": ["Export Incentive Claim", "GST Refund Claim"]},
			{"label": _("Accounts"), "items": ["Journal Entry"]},
		],
	}
