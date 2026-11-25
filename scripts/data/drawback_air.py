"""Build India EXIM's Duty Drawback data pack (All Industry Rates).

    uvx --with pdfplumber python drawback_air.py <csnt77-2023.pdf> <out_dir>

<csnt77-2023.pdf>  Notification 77/2023-Customs (N.T.) dated 20.10.2023, w.e.f. 30.10.2023

The changes made by Notification 33/2024-Customs (N.T.) w.e.f. 03.05.2024 are transcribed below.
Later amendments (26/2025, 51/2025, 21/2026, 41/2026, 64/2026, 85/2026 ...) only change the gold and
silver jewellery entries 711301, 711302 and 711401, whose rates are amounts per gram of fine metal and
change every few months; those entries are left out, so the rate is entered by the user.

The Table after the Schedule (exports against Special Advance Authorisation) is not read.
"""

import csv
import re
import sys
from collections import Counter
from pathlib import Path

import pdfplumber

BASE_FROM, AMENDED_FROM = "2023-10-30", "2024-05-03"
BASE_UPTO = "2024-05-02"
BASE = "Notification 77/2023-Customs (N.T.) dated 20.10.2023"
AMENDMENT = "Notification 77/2023-Customs (N.T.) as amended by 33/2024 dated 30.04.2024"
LEFT_OUT = {"711301", "711302", "711401"}

CODE = re.compile(r"^\d{4}(\d{2}){0,2}$")
RATE = re.compile(r"^(\d+(?:\.\d+)?)\s*%$")
HEADING = re.compile(
	r"CHAPTER|Drawback cap per|Tariff Item|unit in Rs|^\(1\)|^Schedule$|^Drawback$|^Rate$|^Drawback Drawback"
)
NUMBER = re.compile(r"^\d+(\.\d+)?$")

# 33/2024: chapters 3 and 16 and these headings are replaced, then entries are changed or added
REPLACED_CHAPTERS = ("03", "16")
REPLACED_HEADINGS = ("7218", "7222", "7502", "7505", "8108", "8710", "8807", "9301")
NEW_ENTRIES = """
0301|Live fish|Kg|4|12.2
0302|Fish, fresh or chilled, excluding fish fillets and other fish meat of heading 0304|||
030201|In chilled form|Kg|4|27.9
030299|Others||0.15|
0303|Fish, frozen, excluding fish fillets and other fish meat of heading 0304|Kg|4|24.2
0304|Fish fillets and other fish meat (whether or not minced), fresh, chilled or frozen|||
030401|In chilled or frozen form|Kg|4|39.3
030402|Surimi fish paste|Kg|4|10.8
030499|Others||0.15|
0305|Fish, dried, salted or in brine; smoked fish||0.15|
0306|Crustaceans|||
030601|Shrimp/prawn in frozen form other than Accelerated Freeze Dried (AFD)|Kg|3.5|30.8
030602|Accelerated Freeze Dried (AFD) shrimp / prawn|Kg|2.9|123.8
030603|Lobster / Crab|Kg|4.4|74.6
030604|Pasteurised tinned chilled crab meat|Kg|4.5|201
030605|Others in chilled or frozen form|Kg|4.4|46.3
030699|Others||0.15|
0307|Molluscs|||
030701|In chilled or frozen form|Kg|4.5|29.5
030799|Others||0.15|
0308|Aquatic invertebrates other than crustaceans and molluscs|||
030801|In chilled or frozen form|Kg|4.5|24.2
030899|Others||0.15|
0309|Flours, meals and pellets of fish, crustaceans, molluscs and other aquatic invertebrates, fit for human consumption|||
030901|In chilled or frozen form|Kg|2.9|24.2
030999|Others||0.15|
1601|Sausages and similar products, of meat, meat offal, blood or insects; food preparations based on these products||0.15|
1602|Other prepared or preserved meat, meat offal blood or insects||0.15|
1603|Extracts and juices of meat, fish or crustaceans, molluscs or other aquatic invertebrates|||
160301|Of fish or crustaceans in chilled or frozen form|Kg|4|46.3
160399|Others||0.15|
1604|Prepared or preserved fish, caviar and caviar substitutes prepared from fish eggs|||
160401|Surimi analogue product|Kg|4|12.4
160499|Others||0.15|
1605|Crustaceans, molluscs and other aquatic invertebrates, prepared or preserved|||
160501|Shrimp/prawn in frozen form other than Accelerated Freeze Dried (AFD)|||
16050101|Breaded shrimp/prawn|Kg|3.5|23.6
16050199|Others|Kg|3.5|23.6
160502|Accelerated Freeze Dried (AFD) shrimp / prawn|Kg|2.9|91
160503|Lobster / Crab|Kg|4.4|82.2
160504|Pasteurised tinned chilled crab meat|Kg|4.5|201
160505|Others in chilled or frozen form|||
16050501|Breaded Squids|Kg|4.3|53.6
16050599|Others in chilled or frozen form|Kg|4.3|53.6
160599|Others||0.15|
420311|Sports gloves, other than Golf gloves, made of leather|Pair|3.6|14.5
420312|Sports gloves, other than Golf gloves, made of leather in combination with textile materials|Pair|3.6|14.5
7218|Stainless steel in ingots or other primary forms; semi-finished products of stainless steel|||
721801|Containing at least 12% chromium, 7% nickel and 2% molybdenum|Kg|3.1|39
721899|Others||1.5|
7222|Other bars and rods of stainless steel; angles, shapes and sections of stainless steel|||
722201|Containing at least 18% nickel, 2% molybdenum and 1% titanium|Kg|2.1|28
722299|Others||1.5|
722802|Of alloy steel, containing at least 28% nickel and 16% cobalt|Kg|2.1|35
722803|Of alloy steel, containing at least 17% nickel, 4% molybdenum and 7% cobalt|Kg|2.3|70
7502|Unwrought nickel|||
750201|Containing at least 20% chromium, 8% molybdenum and 1% cobalt|Kg|2.4|78
750299|Others||0.15|
7505|Nickel bars, rods, profiles and wire|||
750501|Containing at least 18% chromium and 3% molybdenum||1.3|
750599|Others||0.15|
8108|Titanium and articles thereof, including waste and scrap|||
810801|Containing at least 78% titanium||1.6|
810899|Others||1.2|
8710|Tanks and other armoured fighting vehicles, motorized, and parts of such vehicles|||
871001|Mine protected vehicle||1.6|
871099|Others||0.5|
8807|Parts of goods of heading 8801, 8802 or 8806|||
880701|Gimbal compass for aircraft/spacecraft||7.6|
880702|Optical bench assembly for aircraft/spacecraft||10.2|
880703|Turret for MI-17 helicopter||8.3|
880799|Others||1.7|
9301|Military weapons, other than revolvers, pistols and the arms of heading 9307|||
930101|Towed artillery gun systems||1|
930102|Vehicle mounted artillery gun system||3|
930103|Multi-barrel rocket launchers||1|
930199|Others||0.5|
930602|Missile||0.7|
930699|Others||0.5|
"""
CHANGES = {
	"42020103": {"cap": "74.9"},
	"42020201": {"cap": "251.2"},
	"42020204": {"cap": "144.7"},
	"42020301": {"cap": "78.9"},
	"42020402": {"cap": "33.7"},
	"420303": {"description": "Golf Gloves made of leather", "unit": "Piece"},
	"420304": {
		"description": "Golf Gloves made of leather in combination with textile materials",
		"unit": "Piece",
		"cap": "14.5",
	},
	"420310": {"cap": "36.7"},
	"630201": {"rate": "3", "cap": "68.9"},
	"630202": {"rate": "2.6"},
	"8526": {"rate": "1.3"},
	"8806": {"rate": "1.7"},
}


def group(words):
	lines = []
	for word in sorted(words, key=lambda w: (w["top"], w["x0"])):
		if lines and abs(word["top"] - lines[-1][0]["top"]) < 3:
			lines[-1].append(word)
		else:
			lines.append([word])
	return lines


def lines_of(words):
	"""Words grouped into text lines, top to bottom."""
	return [
		(
			sum(w["top"] for w in line) / len(line),
			" ".join(w["text"] for w in sorted(line, key=lambda w: w["x0"])),
		)
		for line in group(words)
	]


def column(words, left, right):
	return [w for w in words if left <= (w["x0"] + w["x1"]) / 2 < right]


def row_borders(page):
	"""Heights of the thin rules drawn under rows, in the description column."""
	tops = sorted(
		r["top"]
		for r in page.rects
		if r["height"] < 1 and r["x0"] < 300 and r["x1"] > 200 and r["width"] > 60
	)
	return [top for i, top in enumerate(tops) if not i or top - tops[i - 1] > 2]


def page_rows(page):
	"""Rows of one page; every code must have exactly one description block."""
	words, skipped = [], []
	for line in group(page.extract_words()):
		text = " ".join(w["text"] for w in sorted(line, key=lambda w: w["x0"]))
		letters = [c for c in text if c.isalpha()]
		# chapter titles and the column headings of the first page
		if not CODE.match(text.split()[0]) and (
			(len(letters) > 3 and text.upper() == text and not text.startswith("(")) or HEADING.search(text)
		):
			skipped.append(text)
			continue
		words += line
	codes = [(top, text) for top, text in lines_of(column(words, 40, 125)) if CODE.match(text)]
	texts = lines_of(column(words, 125, 312))
	units = lines_of(column(words, 312, 368))
	rates = lines_of(column(words, 368, 446))
	caps = lines_of(column(words, 446, 560))
	borders = row_borders(page)

	def cell(lines):
		cells = {}  # row number -> its lines
		for top, text in lines:
			cells.setdefault(sum(1 for border in borders if border <= top + 4), []).append(text)
		return {row: " ".join(parts) for row, parts in cells.items()}

	texts, units, rates, caps = map(cell, (texts, units, rates, caps))
	rows, used = [], set()
	for y, code in codes:
		number = sum(1 for border in borders if border <= y + 4)
		if number not in texts or number in used:
			raise ValueError(f"no single description for {code} on page {page.page_number}")
		used.add(number)
		rows.append(
			{
				"code": code,
				"description": texts[number],
				"unit": units.get(number, ""),
				"rate": rates.get(number, ""),
				"cap": caps.get(number, ""),
			}
		)
	return rows, skipped, [text for number, text in texts.items() if number not in used]


def read_schedule(path):
	entries, skipped, started, previous = {}, [], False, None
	with pdfplumber.open(path) as pdf:
		for page in pdf.pages:
			text = page.extract_text() or ""
			if not started:
				started = bool(re.search(r"^0101\b", text, re.MULTILINE))
				if not started:
					continue
			if entries and re.search(r"^\s*Table\s*$", text, re.MULTILINE | re.IGNORECASE):
				break
			rows, headings, left = page_rows(page)
			skipped += [(page.page_number, line) for line in headings]
			for line in left:
				if line == left[0] and previous:
					entries[previous]["description"] += " " + line
				else:
					skipped.append((page.page_number, line))
			previous = rows[-1]["code"] if rows else None
			for row in rows:
				if row["code"] in entries:
					raise ValueError(f"{row['code']} appears twice (page {page.page_number})")
				entries[row["code"]] = normalise(row)
	return entries, skipped


def normalise(row):
	rate = re.sub(r"[₹,\s]", "", row["rate"])
	amount, cap = "", re.sub(r"[₹,\s]", "", row["cap"])
	if row["code"] in LEFT_OUT:
		return {**row, "rate": "", "amount": "", "cap": ""}
	if rate.lower() == "nil":
		rate = "0"
	elif match := RATE.match(rate):
		rate = match.group(1)
	elif rate and NUMBER.match(rate):
		rate, amount = "", rate  # an amount in rupees, not a percentage
	elif rate:
		raise ValueError(f"{row['code']}: rate {rate!r}")
	if cap and not NUMBER.match(cap):
		raise ValueError(f"{row['code']}: cap {cap!r}")
	return {**row, "rate": rate, "amount": amount, "cap": cap}


def amend(entries):
	result = {
		code: dict(row)
		for code, row in entries.items()
		if code[:2] not in REPLACED_CHAPTERS and code[:4] not in REPLACED_HEADINGS
	}
	for line in NEW_ENTRIES.strip().splitlines():
		code, description, unit, rate, cap = line.split("|")
		result[code] = {
			"code": code,
			"description": description,
			"unit": unit,
			"rate": rate,
			"amount": "",
			"cap": cap,
		}
	for code, values in CHANGES.items():
		if code not in result:
			raise ValueError(f"33/2024 changes {code}, which is not in the schedule")
		result[code].update(values)
	return result


def full_description(code, entries):
	"""A sub-entry ("Of Cotton") is only clear with the entries above it."""
	parts = [entries[code[:n]]["description"] for n in (4, 6, 8) if n <= len(code) and code[:n] in entries]
	return " > ".join(parts)


def is_leaf(row):
	return row["rate"] != "" or row["amount"] != ""


def build(entries, start, end, notification):
	for code in sorted(entries):
		row = entries[code]
		if not is_leaf(row) or code in LEFT_OUT:
			continue
		yield {
			"serial": code,
			"description": full_description(code, entries),
			"unit": row["unit"],
			"rate": row["rate"],
			"amount_per_unit": row["amount"],
			"cap": row["cap"],
			"effective_from": start,
			"effective_to": end,
			"notification": notification,
		}


def key(row):
	return (row["rate"], row["amount_per_unit"], row["cap"], row["unit"])


def main(pdf_path, out_dir):
	base, skipped = read_schedule(pdf_path)
	amended = amend(base)
	old = {row["serial"]: row for row in build(base, BASE_FROM, BASE_UPTO, BASE)}
	new = {row["serial"]: row for row in build(amended, AMENDED_FROM, "", AMENDMENT)}
	rows = []
	for serial in sorted(set(old) | set(new)):
		before, after = old.get(serial), new.get(serial)
		if before and after and key(before) == key(after):
			rows.append({**before, "effective_to": ""})  # unchanged
		else:
			rows += [row for row in (before, after) if row]
	out = Path(out_dir) / "drawback_air.csv"
	with out.open("w", newline="") as handle:
		writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
		writer.writeheader()
		writer.writerows(rows)
	print("entries", len(base), "with a rate", len(old), "after 33/2024", len(new), "rows", len(rows))
	print("chapters", len({r["serial"][:2] for r in rows}), "units", Counter(r["unit"] for r in rows))
	print("skipped lines:", [s for s in skipped if not s[1].isupper()])


if __name__ == "__main__":
	main(*sys.argv[1:3])
