Free time at the port for the import on **{{ doc.name }}** ({{ doc.supplier_name }}) ends on {{ frappe.format_value(doc.exim_free_time_ends, {"fieldtype": "Date"}) }}.

- BL: {{ doc.exim_bl_number or "-" }}
- CHA: {{ doc.exim_cha or "-" }}

Clear the cargo and return the container before then to avoid detention and demurrage.
