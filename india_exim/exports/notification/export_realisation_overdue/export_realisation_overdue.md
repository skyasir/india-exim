The realisation period for **Shipping Bill {{ doc.shipping_bill_number or doc.name }}** ended on {{ frappe.format_value(doc.realisation_due_date, {"fieldtype": "Date"}) }} and {{ frappe.format_value(doc.outstanding_value, {"fieldtype": "Currency"}, currency=doc.currency) }} is still outstanding.

It will show as overdue in the bank's EDPMS. Record the extension or write-off on the Shipping Bill once the AD bank approves it. Incentives on an unrealised shipment may have to be paid back.
