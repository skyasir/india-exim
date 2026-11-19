Export proceeds against **Shipping Bill {{ doc.shipping_bill_number or doc.name }}** dated {{ frappe.format_value(doc.shipping_bill_date, {"fieldtype": "Date"}) }} must be realised by **{{ frappe.format_value(doc.realisation_due_date, {"fieldtype": "Date"}) }}**.

- Customer: {{ doc.customer_name }}
- Outstanding: {{ frappe.format_value(doc.outstanding_value, {"fieldtype": "Currency"}, currency=doc.currency) }} of {{ frappe.format_value(doc.total_invoice_value, {"fieldtype": "Currency"}, currency=doc.currency) }}
- AD Code: {{ doc.ad_code or "-" }}

Follow up with the buyer, or ask the AD bank for an extension before the due date.
