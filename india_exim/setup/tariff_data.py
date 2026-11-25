"""India EXIM's tariff data: tariff items and export incentive rates taken from the published
DGFT / CBIC schedules (see scripts/data), loaded into each site so users only pick the ITC-HS code.

Each pack is a CSV in setup/data/tariff with a version. A site loads a pack once per version, on
install and on migrate. Every row keeps its dates and notification, so a later version adds the new
rates from their effective date and past documents keep the rate of their own date.

Rates a user entered by hand are never touched: a pack row that would overlap one is skipped.
"""

import csv
import json
from functools import lru_cache
from pathlib import Path

import frappe
from frappe.utils import cstr, flt, getdate, now

from india_exim.utils.validation import OPEN_END

PACK_DIR = Path(__file__).parent / "data" / "tariff"
DEFAULTS_KEY = "india_exim_tariff_data"

PACKS = {
	"rodtep_4r": {
		"version": "2026-05-01",
		"file": "rodtep_4r.csv",
		"scheme": "RoDTEP",
		"source": "RoDTEP Appendix 4R",
	},
	# by schedule serial number instead of ITC-HS code
	"drawback_air": {
		"version": "2024-05-03",
		"file": "drawback_air.csv",
		"scheme": "Duty Drawback",
		"source": "Drawback Schedule 77/2023",
		"by_serial": True,
	},
	"rosctl": {
		"version": "2026-12-31",
		"file": "rosctl.csv",
		"scheme": "RoSCTL",
		"source": "RoSCTL Schedules 1 and 2",
		"by_serial": True,
	},
}

# UQC as printed in the schedules -> ERPNext UOM
UQC_MAP = {
	"kg": "Kg",
	"l": "Litre",
	"m": "Meter",
	"m2": "Square Meter",
	"m3": "Cubic Meter",
	"mt": "Tonne",
	"pa": "Pair",
	"u": "Nos",
	"c/k": "Carat",
	"tu": "Thousand Units",
	"gif/s": "Gram of Fissile Isotopes",
	"piece": "Nos",
	"1no.": "Nos",
	"pair": "Pair",
	"1set": "Set",
	"sq.mtrs.": "Square Meter",
	"sq.ft.": "Square Foot",
	"100pcs": "Hundred Units",
	"1000pcs": "Thousand Units",
	"perkgofsilkcontent": "Kg of Silk Content",
}


def uom_for(uqc: str) -> str | None:
	key = cstr(uqc).replace(" ", "").lower()
	return UQC_MAP.get(key) if key else None


def get_loaded_versions() -> dict:
	return json.loads(frappe.db.get_default(DEFAULTS_KEY) or "{}")


def load_tariff_data(force: bool = False) -> dict:
	"""Load every pack whose version the site does not have yet. Returns a summary per pack."""
	loaded = get_loaded_versions()
	summary = {}
	for key, pack in PACKS.items():
		if not force and loaded.get(key) == pack["version"]:
			continue
		summary[key] = load_incentive_pack(pack)
		loaded[key] = pack["version"]
		frappe.db.set_default(DEFAULTS_KEY, json.dumps(loaded))
	return summary


def read_pack(pack: dict) -> list[dict]:
	with (PACK_DIR / pack["file"]).open(newline="") as handle:
		return list(csv.DictReader(handle))


@lru_cache(maxsize=4)
def get_notified_rates(scheme: str) -> dict[str, list[dict]]:
	"""The rates as published, from the packs of a scheme, by tariff code."""
	rates = {}
	for pack in PACKS.values():
		if pack["scheme"] != scheme or pack.get("by_serial"):
			continue
		for row in read_pack(pack):
			rates.setdefault(row["tariff_code"], []).append(
				{
					"effective_from": getdate(row["effective_from"]),
					"effective_to": getdate(row["effective_to"]) if row["effective_to"] else OPEN_END,
					"rate": flt(row["rate"]),
					"amount_per_unit": flt(row["amount_per_unit"]),
					"cap_per_unit": flt(row["cap"]),
					"notification": row["notification"],
				}
			)
	return rates


def get_notified_rate(scheme: str, tariff: str, on_date) -> dict | None:
	on_date = getdate(on_date)
	for row in get_notified_rates(scheme).get(tariff, []):
		if row["effective_from"] <= on_date <= row["effective_to"]:
			return row
	return None


def differs_from_notified(rate, on_date=None) -> dict | None:
	"""The notified rate when a rate entered by hand differs from it, else None."""
	if rate.get("data_source") or rate.get("schedule_serial_no") or rate.get("item_code"):
		return None
	notified = get_notified_rate(rate.scheme, rate.customs_tariff_item, on_date or rate.effective_from)
	if not notified:
		return None
	keys = ("rate", "amount_per_unit", "cap_per_unit")
	if all(abs(flt(rate.get(key)) - notified[key]) < 0.0001 for key in keys):
		return None
	return notified


def describe(rate) -> str:
	text = (
		f"Rs {flt(rate.get('amount_per_unit'))} per unit"
		if flt(rate.get("amount_per_unit"))
		else f"{flt(rate.get('rate'))}% of FOB"
	)
	if flt(rate.get("cap_per_unit")):
		text += f", cap Rs {flt(rate.get('cap_per_unit'))} per unit"
	return text


def ensure_uoms() -> None:
	for uom in set(UQC_MAP.values()):
		if not frappe.db.exists("UOM", uom):
			frappe.get_doc({"doctype": "UOM", "uom_name": uom}).insert(ignore_permissions=True)


def load_incentive_pack(pack: dict) -> dict:
	rows = read_pack(pack)
	ensure_uoms()
	if pack.get("by_serial"):
		return load_schedule(rows, pack)
	created_tariffs = add_tariff_items(rows, pack["source"])
	created, updated, kept = add_incentive_rates(rows, pack)
	return {
		"tariff_items_created": created_tariffs,
		"rates_created": created,
		"rates_updated": updated,
		"kept_own_rates": kept,
		"own_rates_differing": len(get_own_rates_differing(pack["scheme"])),
	}


def load_schedule(rows: list[dict], pack: dict) -> dict:
	"""Schedule entries (drawback, RoSCTL). They have no tariff item, so rates a user entered for a
	tariff item are separate records and keep winning."""
	scheme, source = pack["scheme"], pack["source"]
	existing = {
		(row.schedule_serial_no, getdate(row.effective_from)): row
		for row in frappe.get_all(
			"Export Incentive Rate",
			filters={"scheme": scheme, "data_source": source},
			fields=["name", "schedule_serial_no", "effective_from"],
			limit=0,
		)
	}
	base = standard_values()
	values, updated = [], 0
	fields = None
	for row in rows:
		record = {
			"description": row["description"],
			"rate": flt(row["rate"]),
			"amount_per_unit": flt(row.get("amount_per_unit")),
			"cap_per_unit": flt(row["cap"]),
			"cap_uom": uom_for(row["unit"]) if row["unit"] else None,
			"central_rate": flt(row.get("central_rate")),
			"central_cap_per_unit": flt(row.get("central_cap")),
			"effective_to": getdate(row["effective_to"]) if row["effective_to"] else None,
			"notification": row["notification"],
		}
		found = existing.get((row["serial"], getdate(row["effective_from"])))
		if found:
			frappe.db.set_value("Export Incentive Rate", found.name, record, update_modified=False)
			updated += 1
			continue
		record.update(
			name=frappe.generate_hash(length=10),
			scheme=scheme,
			schedule_serial_no=row["serial"],
			effective_from=getdate(row["effective_from"]),
			data_source=source,
			**base,
		)
		fields = list(record)
		values.append(tuple(record.values()))
	if values:
		frappe.db.bulk_insert("Export Incentive Rate", fields, values)
	return {
		"tariff_items_created": 0,
		"rates_created": len(values),
		"rates_updated": updated,
		"kept_own_rates": 0,
		"own_rates_differing": 0,
	}


def get_own_rates_differing(scheme: str) -> list[str]:
	"""Rates entered by hand that differ from the notified rate for their start date."""
	own = frappe.get_all(
		"Export Incentive Rate",
		filters={
			"scheme": scheme,
			"data_source": ("is", "not set"),
			"schedule_serial_no": ("is", "not set"),
			"item_code": ("is", "not set"),
		},
		fields=[
			"name",
			"scheme",
			"customs_tariff_item",
			"effective_from",
			"rate",
			"amount_per_unit",
			"cap_per_unit",
		],
	)
	return [rate.name for rate in own if differs_from_notified(rate)]


def standard_values() -> dict:
	timestamp = now()
	user = frappe.session.user or "Administrator"
	return {"creation": timestamp, "modified": timestamp, "owner": user, "modified_by": user, "docstatus": 0}


def add_tariff_items(rows: list[dict], source: str) -> int:
	"""Tariff items the site does not have yet. Their trade policy is left empty (not checked)."""
	existing = set(frappe.get_all("Customs Tariff Item", pluck="name"))
	hsn_codes = set(frappe.get_all("GST HSN Code", pluck="name"))
	base = standard_values()
	fields = [
		"name",
		"tariff_code",
		"description",
		"chapter",
		"uqc",
		"gst_hsn_code",
		"export_policy",
		"import_policy",
		"data_source",
		*base,
	]
	values, seen = [], set()
	for row in rows:
		code = row["tariff_code"]
		if code in existing or code in seen:
			continue
		seen.add(code)
		values.append(
			(
				code,
				code,
				row["description"] or code,
				code[:2],
				uom_for(row["uqc"]),
				code if code in hsn_codes else None,
				"",
				"",
				source,
				*base.values(),
			)
		)
	if values:
		frappe.db.bulk_insert("Customs Tariff Item", fields, values, ignore_duplicates=True)
	return len(values)


def overlaps(start, end, periods) -> bool:
	start, end = getdate(start), getdate(end) if end else OPEN_END
	return any(start <= other_end and other_start <= end for other_start, other_end in periods)


def add_incentive_rates(rows: list[dict], pack: dict) -> tuple[int, int, int]:
	scheme, source = pack["scheme"], pack["source"]
	current = frappe.get_all(
		"Export Incentive Rate",
		filters={"scheme": scheme, "schedule_serial_no": ("is", "not set"), "item_code": ("is", "not set")},
		fields=[
			"name",
			"customs_tariff_item",
			"effective_from",
			"effective_to",
			"rate",
			"amount_per_unit",
			"cap_per_unit",
			"notification",
			"data_source",
		],
	)
	from_pack, own_periods = {}, {}
	for rate in current:
		if rate.data_source == source:
			from_pack[(rate.customs_tariff_item, getdate(rate.effective_from))] = rate
		else:
			own_periods.setdefault(rate.customs_tariff_item, []).append(
				(getdate(rate.effective_from), getdate(rate.effective_to) if rate.effective_to else OPEN_END)
			)

	base = standard_values()
	fields = [
		"name",
		"scheme",
		"customs_tariff_item",
		"description",
		"rate",
		"amount_per_unit",
		"cap_per_unit",
		"cap_uom",
		"effective_from",
		"effective_to",
		"notification",
		"data_source",
		*base,
	]
	values, updated, kept = [], 0, set()
	for row in rows:
		code = row["tariff_code"]
		effective_from = getdate(row["effective_from"])
		effective_to = getdate(row["effective_to"]) if row["effective_to"] else None
		amounts = {
			"rate": flt(row["rate"]),
			"amount_per_unit": flt(row["amount_per_unit"]),
			"cap_per_unit": flt(row["cap"]),
			"effective_to": effective_to,
			"notification": row["notification"],
		}
		existing = from_pack.get((code, effective_from))
		if existing:
			if any(
				(getdate(existing[key]) if key == "effective_to" and existing[key] else existing[key])
				!= value
				for key, value in amounts.items()
			):
				frappe.db.set_value("Export Incentive Rate", existing.name, amounts, update_modified=True)
				updated += 1
			continue
		if overlaps(effective_from, effective_to, own_periods.get(code, [])):
			kept.add(code)
			continue
		unit = uom_for(row["uqc"]) if (amounts["cap_per_unit"] or amounts["amount_per_unit"]) else None
		values.append(
			(
				frappe.generate_hash(length=10),
				scheme,
				code,
				row["description"][:140],
				amounts["rate"],
				amounts["amount_per_unit"],
				amounts["cap_per_unit"],
				unit,
				effective_from,
				effective_to,
				row["notification"],
				source,
				*base.values(),
			)
		)
	if values:
		frappe.db.bulk_insert("Export Incentive Rate", fields, values)
	return len(values), updated, len(kept)


@frappe.whitelist()
def reload_tariff_data() -> dict:
	"""Load the tariff data again (India EXIM Settings > Reload Tariff Data)."""
	frappe.only_for("System Manager")
	return load_tariff_data(force=True)


@frappe.whitelist()
def use_notified_rates(name: str) -> int:
	"""Replace a rate entered by hand with the notified rates for its scheme and tariff item."""
	rate = frappe.get_doc("Export Incentive Rate", name)
	rate.check_permission("delete")
	if rate.data_source:
		frappe.throw(frappe._("This rate is already the notified rate."))
	pack = next(
		(pack for pack in PACKS.values() if pack["scheme"] == rate.scheme and not pack.get("by_serial")), None
	)
	rows = [row for row in read_pack(pack) if row["tariff_code"] == rate.customs_tariff_item] if pack else []
	if not rows:
		frappe.throw(frappe._("India EXIM's tariff data has no notified rate for this tariff item."))
	others = frappe.get_all(
		"Export Incentive Rate",
		filters={
			"scheme": rate.scheme,
			"customs_tariff_item": rate.customs_tariff_item,
			"data_source": ("is", "not set"),
			"schedule_serial_no": ("is", "not set"),
			"item_code": ("is", "not set"),
		},
		pluck="name",
	)
	for other in others:
		frappe.delete_doc("Export Incentive Rate", other)
	created, _updated, _kept = add_incentive_rates(rows, pack)
	return created


@frappe.whitelist()
def get_notified_for_rate(name: str) -> dict | None:
	"""For the Export Incentive Rate form: the notified rate when this rate differs from it."""
	rate = frappe.get_doc("Export Incentive Rate", name)
	rate.check_permission("read")
	notified = differs_from_notified(rate)
	return {**notified, "text": describe(notified)} if notified else None
