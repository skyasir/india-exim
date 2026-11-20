def render_print_format(doc, print_format: str | None = None) -> str:
	"""The body of a print format for a document, without the print page around it.

	frappe.get_print wraps the body in the print view page, which needs the built print
	stylesheet; this works wherever Jinja does (background jobs, tests, sites without built assets).
	"""
	import frappe
	from frappe.www.printview import get_rendered_template

	return get_rendered_template(
		doc,
		print_format=frappe.get_doc("Print Format", print_format) if print_format else None,
		no_letterhead=1,
	)
