"""Build India EXIM's RoDTEP data pack from DGFT's published PDFs.

    uvx --with pdfplumber python rodtep_4r.py <appendix_4r.pdf> <changes.pdf> <out_dir>

<appendix_4r.pdf>  Appendix 4R w.e.f. 10.10.2024 (Notification 32/2023-28, 30.09.2024)
<changes.pdf>      Changes in Appendix 4R and 4RE w.e.f. 01.05.2026 (Notification 15/2026-27)

Writes rodtep_4r.csv: one row per tariff item and period, with the notification it comes from.
Rows read from the PDFs are checked (8-digit code, rate and cap numbers) and counted, so a layout
change in a future PDF fails loudly instead of producing wrong rates.
"""

import csv
import re
import sys
from collections import Counter
from pathlib import Path

import pdfplumber

BASE = {"effective_from": "2024-10-10", "notification": "DGFT Notification 32/2023-28 dated 30.09.2024"}
MAY_2026 = {"effective_from": "2026-05-01", "notification": "DGFT Notification 15/2026-27 dated 30.04.2026"}
# RoDTEP is notified up to a date and extended by notification; rates end with the scheme
SCHEME_UPTO = "2026-12-31"  # DGFT Notification 41/2026-27 dated 30.09.2026

CODE = re.compile(r"^\d{8}$")
NUMBER = re.compile(r"^\d+(\.\d+)?$")


def clean(text):
	return " ".join((text or "").split())


def rate(text):
	"""(rate % of FOB, fixed amount in Rs per UQC). A few entries give a fixed amount, e.g. "Rs. 280"."""
	value = clean(text).replace(" ", "")
	if value.upper() == "NIL":  # listed in the schedule with no benefit
		return "0", ""
	if value.lower().startswith("rs"):
		amount = value[2:].lstrip(".")
		if not NUMBER.match(amount):
			raise ValueError(f"amount {text!r}")
		return "", amount
	value = value.replace("%", "")
	if not NUMBER.match(value):
		raise ValueError(f"rate {text!r}")
	return value, ""


def cap(text):
	value = clean(text).replace(",", "").replace(" ", "")
	if value and not NUMBER.match(value):
		raise ValueError(f"cap {text!r}")
	return value


def make_entry(code, description, uqc, rate_text, cap_text):
	percent, amount = rate(rate_text)
	return {
		"tariff_code": code,
		"description": description,
		"uqc": uqc,
		"rate": percent,
		"amount_per_unit": amount,
		"cap": cap(cap_text),
	}


def rows_of(pdf_path, pages=None):
	with pdfplumber.open(pdf_path) as pdf:
		for index, page in enumerate(pdf.pages):
			if pages and index not in pages:
				continue
			for table in page.extract_tables():
				for row in table:
					cells = [clean(cell) for cell in row]
					if len(cells) >= 2 and CODE.match(cells[1]):
						yield index, cells


def read_schedule(pdf_path):
	"""(code -> row) from a full schedule: entry, code, description, UQC, rate, cap."""
	schedule = {}
	for _, cells in rows_of(pdf_path):
		_entry, code, description, uqc, rate_text, cap_text = cells[:6]
		if code in schedule:
			raise ValueError(f"{code} appears twice")
		schedule[code] = make_entry(code, description, uqc, rate_text, cap_text)
	return schedule


def read_changes(pdf_path):
	"""Annexure A (4R additions), C (omitted, 4R and 4RE), D (4R description changes)."""
	added, omitted, renamed = {}, set(), {}
	with pdfplumber.open(pdf_path) as pdf:
		sections = {}
		for index, page in enumerate(pdf.pages):
			text = page.extract_text() or ""
			match = re.search(r"Annexure-([A-E])", text)
			if match:
				sections[index] = match.group(1)
	for index, cells in rows_of(pdf_path):
		section = sections[index]
		if section == "A":
			_, code, description, uqc, rate_text, cap_text = cells[:6]
			added[code] = make_entry(code, description, uqc, rate_text, cap_text)
		elif section == "C":
			omitted.add(cells[1])
		elif section == "D":
			# Sr, code, old description, new description, UQC, rate, cap
			renamed[cells[1]] = cells[3]
	return added, omitted, renamed


def main(appendix, changes, out_dir):
	schedule = read_schedule(appendix)
	added, omitted, renamed = read_changes(changes)
	rows = []
	for code, row in sorted(schedule.items()):
		ends = "2026-04-30" if code in omitted else SCHEME_UPTO
		rows.append(
			{**row, **BASE, "effective_to": ends, "description": renamed.get(code, row["description"])}
		)
	for code, row in sorted(added.items()):
		if code in schedule:
			raise ValueError(f"{code} added in 2026 but already in the 2024 schedule")
		rows.append({**row, **MAY_2026, "effective_to": SCHEME_UPTO})

	missing = omitted - set(schedule)
	print(f"2024 schedule: {len(schedule)} tariff items")
	print(f"May 2026: {len(added)} added to 4R, {len(omitted)} omitted (4R and 4RE), {len(renamed)} renamed")
	if missing:
		print(f"omitted but not in 4R (4RE only): {len(missing)}")

	out = Path(out_dir) / "rodtep_4r.csv"
	fields = [
		"tariff_code",
		"description",
		"uqc",
		"rate",
		"amount_per_unit",
		"cap",
		"effective_from",
		"effective_to",
		"notification",
	]
	with out.open("w", newline="") as handle:
		writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
		writer.writeheader()
		writer.writerows(rows)
	print(f"wrote {len(rows)} rows to {out}")
	print("UQC used:", dict(sorted(Counter(row["uqc"] for row in rows).items())))


if __name__ == "__main__":
	main(*sys.argv[1:4])
