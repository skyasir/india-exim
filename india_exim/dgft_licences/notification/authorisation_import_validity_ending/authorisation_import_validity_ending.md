Imports under **{{ doc.scheme }} {{ doc.authorisation_number }}** are allowed until {{ frappe.format_value(doc.import_validity_upto, {"fieldtype": "Date"}) }}.

CIF imported so far: {{ frappe.format_value(doc.total_cif_imported, {"fieldtype": "Currency"}) }} of {{ frappe.format_value(doc.total_cif_allowed, {"fieldtype": "Currency"}) }} allowed.

Clear any pending imports before then, or apply to DGFT to revalidate.
