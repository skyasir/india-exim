"""Build India EXIM's RoSCTL data pack.

    uvx --with pdfplumber python rosctl.py <rosctl_2019.pdf> <out_dir>

<rosctl_2019.pdf>  Ministry of Textiles Notification 14/26/2016-IT (Vol.II) dated 08.03.2019:
                   Schedule 1 (State) and Schedule 2 (Central) for apparel and made-ups

The rates have been continued unchanged since; the one change is FIBC (630501), 2.3% with a cap of
Rs 3.7 per Kg from 09.02.2024 (addendum 19.02.2024). Schedules 3 and 4 (Special Advance Authorisation)
are not read. The scheme is notified up to 31.12.2026 (notification dated 30.09.2026).
"""

import csv
import re
import sys
from collections import Counter
from pathlib import Path

import pdfplumber

START, UPTO = "2019-03-07", "2026-12-31"
NOTIFICATION = "Ministry of Textiles Notification 14/26/2016-IT (Vol.II) dated 08.03.2019"
FIBC = {
	"serial": "630501",
	"description": "Sacks and bags, of a kind used for the packing of goods > Flexible Intermediate Bulk Containers (FIBC)",
	"unit": "Kg",
	"rate": "2.3",  # notified as one rate, not split into State and Central
	"cap": "3.7",
	"central_rate": "",
	"central_cap": "",
	"effective_from": "2024-02-09",
	"effective_to": UPTO,
	"notification": "Ministry of Textiles notification dated 09.02.2024 (FIBC) and addendum 19.02.2024",
}
CODE = re.compile(r"^(\d{4}(?:\d{2}){0,2})\b\s*(.*)$")
VALUES = re.compile(
	r"^(?P<text>.*?)\s*(?P<unit>Piece|Pieces|Kg|Pair|Sq\.? ?[Mm]trs?\.?|Set|1 Set|No\.?|Dozen)?\s+"
	r"(?P<rate>\d{1,2}\.\d{1,2})(?:\s+(?P<cap>\d+(?:\.\d+)?))?$"
)
SKIP = re.compile(r"abcaus|GAZETTE|CHAPTER|Tariff Item|Cap per|^Rs\.?$|^1 2 3 4 5$|^[A-Z ,\-\u2013;&']+$")


def read(path):
	schedules, current, entry = {}, None, None
	with pdfplumber.open(path) as pdf:
		for page in pdf.pages:
			for line in (page.extract_text() or "").split("\n"):
				line = " ".join(line.split())
				if match := re.match(r"^Schedule (\d)\s*:", line):
					current, entry = match.group(1), None
					schedules.setdefault(current, {})
					continue
				if current is None or not line or SKIP.search(line):
					continue
				if match := CODE.match(line):
					code, rest = match.groups()
					entry = {"code": code, "description": rest, "unit": "", "rate": "", "cap": ""}
					if values := VALUES.match(rest):
						entry.update(
							description=values["text"],
							unit=values["unit"] or "",
							rate=values["rate"],
							cap=values["cap"] or "",
						)
					if code in schedules[current]:
						raise ValueError(f"{code} appears twice in Schedule {current}")
					schedules[current][code] = entry
				elif entry:
					if not entry["rate"] and (values := VALUES.match(line)):
						entry.update(unit=values["unit"] or "", rate=values["rate"], cap=values["cap"] or "")
						line = values["text"]
					entry["description"] = f"{entry['description']} {line}".strip()
	return schedules


def full_description(code, entries):
	return " > ".join(
		entries[code[:n]]["description"] for n in (4, 6, 8) if n <= len(code) and code[:n] in entries
	)


def main(pdf_path, out_dir):
	schedules = read(pdf_path)
	state = {c: e for c, e in schedules["1"].items() if e["rate"]}
	central = {c: e for c, e in schedules["2"].items() if e["rate"]}
	if set(state) != set(central):
		raise ValueError(f"State and Central differ: {sorted(set(state) ^ set(central))}")
	rows = []
	for code in sorted(state):
		s, c = state[code], central[code]
		if s["unit"] != c["unit"]:
			raise ValueError(f"{code}: units {s['unit']!r} and {c['unit']!r}")
		rows.append(
			{
				"serial": code,
				"description": full_description(code, schedules["1"]),
				"unit": s["unit"],
				"rate": s["rate"],
				"cap": s["cap"],
				"central_rate": c["rate"],
				"central_cap": c["cap"],
				"effective_from": START,
				"effective_to": UPTO,
				"notification": NOTIFICATION,
			}
		)
	rows.append(FIBC)
	rows.sort(key=lambda row: row["serial"])
	out = Path(out_dir) / "rosctl.csv"
	with out.open("w", newline="") as handle:
		writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
		writer.writeheader()
		writer.writerows(rows)
	print({k: len(v) for k, v in schedules.items()}, "rows", len(rows), Counter(r["unit"] for r in rows))
	print(
		Counter(r["serial"][:2] for r in rows), [r["serial"] for r in rows if r["serial"].startswith("6305")]
	)


if __name__ == "__main__":
	main(*sys.argv[1:3])
