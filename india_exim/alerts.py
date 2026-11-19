"""Daily alerts that the standard Notification doctype cannot express.

Date-based alerts on a single document (realisation due, LUT expiry, scrip expiry, free time,
import payment) are standard Notifications shipped in each module's `notification` folder, so
clients can edit or disable them. The two here look at child rows or at the absence of a record.
"""

import frappe
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
from frappe.utils import add_days, get_link_to_form, getdate
from frappe.utils.user import get_users_with_role

STALE_RATE_DAYS = 16  # CBIC notifies customs exchange rates twice a month
OPEN_DOCUMENT_STATUSES = ("Pending", "Applied", "Discrepancy")
CLOSED_SHIPMENT_STATUSES = ("Delivered", "Closed", "Cancelled")


def send_daily_alerts() -> None:
	notify_document_deadlines()
	notify_missing_customs_exchange_rate()


def notify_document_deadlines() -> None:
	"""Tell the responsible user (or the shipment owner) about checklist documents due in
	two days or that became overdue yesterday. One alert per shipment and user."""
	today = getdate()
	shipment = frappe.qb.DocType("Export Shipment")
	document = frappe.qb.DocType("Shipment Document")
	rows = (
		frappe.qb.from_(document)
		.join(shipment)
		.on((shipment.name == document.parent) & (document.parenttype == "Export Shipment"))
		.select(
			shipment.name.as_("shipment"),
			shipment.customer_name,
			shipment.owner,
			document.document_type,
			document.due_date,
			document.responsible,
		)
		.where(shipment.status.notin(CLOSED_SHIPMENT_STATUSES))
		.where(document.status.isin(OPEN_DOCUMENT_STATUSES))
		.where(document.mandatory == 1)
		.where(document.due_date.isin([add_days(today, 2), add_days(today, -1)]))
	).run(as_dict=True)

	grouped = {}
	for row in rows:
		key = (row.shipment, row.responsible or row.owner)
		grouped.setdefault(key, {"row": row, "due": [], "overdue": []})
		bucket = "overdue" if getdate(row.due_date) < today else "due"
		grouped[key][bucket].append(row.document_type)

	for (shipment_name, user), item in grouped.items():
		lines = []
		if item["overdue"]:
			lines.append(_("Overdue: {0}").format(", ".join(item["overdue"])))
		if item["due"]:
			lines.append(_("Due in 2 days: {0}").format(", ".join(item["due"])))
		enqueue_create_notification(
			user,
			{
				"type": "Alert",
				"document_type": "Export Shipment",
				"document_name": shipment_name,
				"subject": _("Shipment documents for {0}: {1}").format(
					item["row"].customer_name or shipment_name, "; ".join(lines)
				),
				"email_content": "<br>".join(lines)
				+ "<br><br>"
				+ get_link_to_form("Export Shipment", shipment_name),
			},
		)


def notify_missing_customs_exchange_rate() -> None:
	"""Warn EXIM Managers when no customs exchange rate has been entered for the current
	fortnight, since shipping bills and bills of entry would pick up an old rate. Sent on the
	2nd and 17th, a day after CBIC's usual notification dates."""
	today = getdate()
	if today.day not in (2, 17) or not frappe.db.count("Customs Exchange Rate"):
		return

	latest = frappe.db.get_value(
		"Customs Exchange Rate", {}, "effective_from", order_by="effective_from desc"
	)
	if latest and getdate(latest) > add_days(today, -STALE_RATE_DAYS):
		return

	users = get_users_with_role("EXIM Manager")
	if not users:
		return
	enqueue_create_notification(
		users,
		{
			"type": "Alert",
			"document_type": "Customs Exchange Rate",
			"subject": _("No customs exchange rate entered for this fortnight (latest: {0})").format(
				frappe.format_value(latest, {"fieldtype": "Date"}) if latest else _("none")
			),
			"email_content": _(
				"Enter the rates from the latest CBIC notification so that new shipping bills and bills of entry use them."
			),
		},
	)
