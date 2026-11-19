import frappe

from india_exim.setup.accounts import setup_exim_accounts


def after_insert(doc, method=None):
	if doc.country == "India":
		setup_exim_accounts(doc.name)


@frappe.whitelist()
def create_default_exim_accounts(company: str) -> None:
	frappe.has_permission("Company", "write", company, throw=True)
	setup_exim_accounts(company)
