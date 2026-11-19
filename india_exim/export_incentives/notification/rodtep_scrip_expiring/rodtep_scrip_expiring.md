**RoDTEP scrip {{ doc.scrip_number }}** expires on {{ frappe.format_value(doc.valid_upto, {"fieldtype": "Date"}) }} with a balance of {{ frappe.format_value(doc.balance_amount, {"fieldtype": "Currency"}) }}.

Use it against customs duty on a Bill of Entry, or sell it, before it lapses.
