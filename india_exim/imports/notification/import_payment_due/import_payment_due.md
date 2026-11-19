Payment for the goods on **Bill of Entry {{ doc.bill_of_entry_no or doc.name }}** dated {{ frappe.format_value(doc.bill_of_entry_date, {"fieldtype": "Date"}) }} is due by {{ frappe.format_value(doc.exim_payment_due_date, {"fieldtype": "Date"}) }}.

- Invoice value: {{ frappe.format_value(doc.exim_invoice_value, {"fieldtype": "Currency"}, currency=doc.exim_currency) }}
- Paid so far: {{ frappe.format_value(doc.exim_paid_value, {"fieldtype": "Currency"}, currency=doc.exim_currency) }}

Unpaid Bills of Entry stay open in the bank's IDPMS until the remittance is made.
