"""Evidence pack: everything about one Shipping Bill or Bill of Entry in a single ZIP, for a
customs post-clearance audit, a DGFT or RBI enquiry, or the statutory auditor.

It holds PDFs of the documents (in the India EXIM print formats where there is one), every file
attached to them, the payments and journal entries that settle or account for them, and the
change history (Version log) of each document, with an index of what is inside.
"""

import csv
import io
import json
import zipfile

import frappe
from frappe import _
from frappe.utils import cstr, get_datetime

SUPPORTED = ("Shipping Bill", "Bill of Entry")
PRINT_FORMATS = {
	"Sales Invoice": ["Export Commercial Invoice", "Export Packing List"],
	"Export Shipment": ["Shipping Instructions"],
	"Purchase Invoice": ["Import Clearing Instructions"],
}


@frappe.whitelist()
def download_evidence_pack(doctype: str, name: str) -> None:
	if doctype not in SUPPORTED:
		frappe.throw(_("An evidence pack can be made for a Shipping Bill or a Bill of Entry."))
	frappe.get_doc(doctype, name).check_permission("read")
	frappe.local.response.filename = f"Evidence Pack - {doctype} {name}.zip".replace("/", "-")
	frappe.local.response.filecontent = build_evidence_pack(doctype, name)
	frappe.local.response.type = "download"


def build_evidence_pack(doctype: str, name: str) -> bytes:
	documents = get_related_documents(doctype, name)
	index, buffer = [], io.BytesIO()
	with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as pack:
		for number, (related_doctype, related_name, role) in enumerate(documents, start=1):
			if not frappe.has_permission(related_doctype, "read", related_name):
				index.append([number, related_doctype, related_name, role, _("Skipped: no permission")])
				continue
			folder = f"{number:02d} {related_doctype} {related_name}".replace("/", "-")
			files = add_prints(pack, folder, related_doctype, related_name)
			files += add_attachments(pack, folder, related_doctype, related_name)
			index.append([number, related_doctype, related_name, role, ", ".join(files)])
		pack.writestr("audit_trail.csv", to_csv(get_audit_trail(documents)))
		pack.writestr(
			"index.csv",
			to_csv([[_("No."), _("Document Type"), _("Document"), _("Role"), _("Files")], *index]),
		)
	return buffer.getvalue()


def get_related_documents(doctype: str, name: str) -> list[tuple[str, str, str]]:
	"""(doctype, name, role) of the document and everything that evidences it, in reading order."""
	doc = frappe.get_doc(doctype, name)
	related = [(doctype, name, _("Main document"))]
	if doctype == "Shipping Bill":
		invoices = sorted({row.sales_invoice for row in doc.items if row.sales_invoice})
		related += [("Sales Invoice", invoice, _("Export invoice")) for invoice in invoices]
		if doc.export_shipment:
			related.append(("Export Shipment", doc.export_shipment, _("Shipment and document checklist")))
		related += [
			("Export Incentive Claim", claim, _("Incentive claim"))
			for claim in frappe.get_all(
				"Export Incentive Claim Item",
				filters={"shipping_bill": name, "docstatus": 1},
				pluck="parent",
				distinct=True,
			)
		]
		related += [
			("Sales Invoice", note, _("Credit note")) for note in get_returns("Sales Invoice", invoices)
		]
		related += get_settlements("Sales Invoice", invoices)
	else:
		invoices = sorted({row.purchase_invoice for row in doc.items if row.purchase_invoice})
		related += [("Purchase Invoice", invoice, _("Import invoice")) for invoice in invoices]
		related += [
			("Landed Cost Voucher", voucher, _("Landed cost"))
			for voucher in frappe.get_all(
				"Landed Cost Purchase Receipt",
				filters={"receipt_document": ("in", invoices or [""]), "docstatus": 1},
				pluck="parent",
				distinct=True,
			)
		]
		related += get_settlements("Purchase Invoice", invoices)

	related += [
		("Journal Entry", entry, _("EXIM accounting entry"))
		for entry in frappe.get_all(
			"Journal Entry",
			filters={"exim_reference_type": doctype, "exim_reference_name": name, "docstatus": 1},
			pluck="name",
		)
	]
	seen, unique = set(), []
	for row in related:
		if (row[0], row[1]) not in seen:
			seen.add((row[0], row[1]))
			unique.append(row)
	return unique


def get_returns(doctype: str, invoices: list[str]) -> list[str]:
	if not invoices:
		return []
	return frappe.get_all(
		doctype, filters={"return_against": ("in", invoices), "is_return": 1, "docstatus": 1}, pluck="name"
	)


def get_settlements(doctype: str, invoices: list[str]) -> list[tuple[str, str, str]]:
	"""Payment and journal entries that settled the invoices (from the Payment Ledger)."""
	if not invoices:
		return []
	rows = frappe.get_all(
		"Payment Ledger Entry",
		filters={
			"against_voucher_type": doctype,
			"against_voucher_no": ("in", invoices),
			"voucher_type": ("in", ("Payment Entry", "Journal Entry")),
			"delinked": 0,
		},
		fields=["voucher_type", "voucher_no"],
		distinct=True,
	)
	return [(row.voucher_type, row.voucher_no, _("Payment / settlement")) for row in rows]


def add_prints(pack: zipfile.ZipFile, folder: str, doctype: str, name: str) -> list[str]:
	formats = PRINT_FORMATS.get(doctype) or [None]
	added = []
	for print_format in formats:
		label = print_format or doctype
		try:
			content = frappe.get_print(doctype, name, print_format, as_pdf=True)
			filename = f"{label}.pdf"
		except Exception:
			# no PDF engine available: keep the HTML so the pack is still complete
			content = frappe.get_print(doctype, name, print_format)
			filename = f"{label}.html"
		pack.writestr(f"{folder}/{filename}", content)
		added.append(filename)
	return added


def add_attachments(pack: zipfile.ZipFile, folder: str, doctype: str, name: str) -> list[str]:
	added = []
	for file in frappe.get_all(
		"File",
		filters={"attached_to_doctype": doctype, "attached_to_name": name, "is_folder": 0},
		fields=["name", "file_name"],
	):
		try:
			content = frappe.get_doc("File", file.name).get_content()
		except Exception:
			continue
		filename = f"attachments/{file.file_name}"
		pack.writestr(f"{folder}/{filename}", content)
		added.append(filename)
	return added


def get_audit_trail(documents: list[tuple[str, str, str]]) -> list[list]:
	rows = [[_("Document Type"), _("Document"), _("Changed On"), _("Changed By"), _("Changes")]]
	for doctype, name, _role in documents:
		for version in frappe.get_all(
			"Version",
			filters={"ref_doctype": doctype, "docname": name},
			fields=["creation", "owner", "data"],
			order_by="creation",
		):
			rows.append(
				[doctype, name, get_datetime(version.creation), version.owner, describe(version.data)]
			)
	return rows


def describe(data: str) -> str:
	try:
		changes = json.loads(data or "{}")
	except ValueError:
		return ""
	parts = [f"{field}: {cstr(old)} -> {cstr(new)}" for field, old, new in changes.get("changed") or []]
	if changes.get("added"):
		parts.append(_("{0} row(s) added").format(len(changes["added"])))
	if changes.get("removed"):
		parts.append(_("{0} row(s) removed").format(len(changes["removed"])))
	if changes.get("row_changed"):
		parts.append(_("{0} row(s) changed").format(len(changes["row_changed"])))
	if changes.get("comment"):
		parts.append(cstr(changes["comment"]))
	return "; ".join(parts)


def to_csv(rows: list[list]) -> str:
	out = io.StringIO()
	csv.writer(out).writerows(rows)
	return out.getvalue()
