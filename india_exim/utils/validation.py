import itertools

import frappe
from frappe import _
from frappe.utils import formatdate, getdate

OPEN_END = getdate("9999-12-31")


def validate_period(effective_from, effective_to, label: str = "") -> None:
	if effective_to and getdate(effective_to) < getdate(effective_from):
		frappe.throw(
			_("{0}Effective To cannot be before Effective From.").format(f"{label}: " if label else "")
		)


def validate_no_overlap(periods: list[tuple], label: str) -> None:
	"""periods: (effective_from, effective_to or None). Raises when two periods overlap."""
	ordered = sorted((getdate(start), getdate(end) if end else OPEN_END) for start, end in periods)
	for (_start, previous_end), (start, _end) in itertools.pairwise(ordered):
		if start <= previous_end:
			frappe.throw(
				_("{0} has overlapping validity periods around {1}.").format(label, formatdate(start)),
				title=_("Overlapping Rates"),
			)
