**Shipping Bill {{ doc.shipping_bill_number or doc.name }}** got its Let Export Order on {{ frappe.format_value(doc.leo_date, {"fieldtype": "Date"}) }} and is not on any Export Incentive Claim yet.

- Duty Drawback accrued: {{ frappe.format_value(doc.total_drawback, {"fieldtype": "Currency"}) }}
- RoDTEP accrued: {{ frappe.format_value(doc.total_rodtep, {"fieldtype": "Currency"}) }}

Create an Export Incentive Claim once the drawback scroll or RoDTEP claim is generated.
