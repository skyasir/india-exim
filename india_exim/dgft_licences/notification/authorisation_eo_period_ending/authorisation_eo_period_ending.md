The export obligation period of **{{ doc.scheme }} {{ doc.authorisation_number }}** ends on {{ frappe.format_value(doc.eo_period_upto, {"fieldtype": "Date"}) }}.

- Obligation: {{ frappe.format_value(doc.eo_required, {"fieldtype": "Currency"}) }}
- Fulfilled so far: {{ frappe.format_value(doc.eo_fulfilled, {"fieldtype": "Currency"}) }} ({{ doc.eo_percent | round(1) }}%)
- Balance: {{ frappe.format_value(doc.eo_balance, {"fieldtype": "Currency"}) }}

Plan the remaining exports, or apply to DGFT for an extension before the period ends. An unmet obligation has to be regularised by paying the duty saved with interest.
