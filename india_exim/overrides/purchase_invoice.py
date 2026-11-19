from frappe.utils import add_days, cint


def set_free_time_end(doc, method=None):
	"""Detention / demurrage free time runs from actual arrival."""
	arrival = doc.get("exim_ata") or doc.get("exim_eta")
	doc.exim_free_time_ends = (
		add_days(arrival, cint(doc.get("exim_free_days"))) if arrival and doc.get("exim_free_days") else None
	)
