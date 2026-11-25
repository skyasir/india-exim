"""Generate Frappe DocType JSON (+ stub controller) from compact specs.

Field spec: "fieldname:Fieldtype:Label|opt=..|reqd|ro|list|..."  or a dict.
Only JSON is (re)written; existing .py controllers are never overwritten.
"""

import json
import re
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1] / "india_exim"
TS = "2026-11-19 20:00:00.000000"

FLAGS = {
	"reqd": ("reqd", 1),
	"ro": ("read_only", 1),
	"list": ("in_list_view", 1),
	"filter": ("in_standard_filter", 1),
	"hidden": ("hidden", 1),
	"bold": ("bold", 1),
	"unique": ("unique", 1),
	"nocopy": ("no_copy", 1),
	"aos": ("allow_on_submit", 1),
	"collapsible": ("collapsible", 1),
	"dashboard": ("show_dashboard", 1),
	"phide": ("print_hide", 1),
	"search": ("search_index", 1),
	"translatable": ("translatable", 1),
}
KEYS = {
	"opt": "options",
	"default": "default",
	"depends": "depends_on",
	"mandatory_depends": "mandatory_depends_on",
	"ro_depends": "read_only_depends_on",
	"fetch": "fetch_from",
	"desc": "description",
	"precision": "precision",
	"length": "length",
	"width": "columns",
	"if_empty": "fetch_if_empty",
	"link_filters": "link_filters",
}


def parse_field(spec):
	if isinstance(spec, dict):
		return spec
	head, *rest = spec.split("|")
	fieldname, fieldtype, *label = head.split(":", 2)
	field = {"fieldname": fieldname, "fieldtype": fieldtype}
	if label and label[0]:
		field["label"] = label[0]
	for token in rest:
		if "=" in token:
			key, value = token.split("=", 1)
			value = value.replace("\\n", "\n")
			key = KEYS[key]
			if key in ("columns", "length", "fetch_if_empty"):
				value = int(value)
			field[key] = value
		else:
			name, value = FLAGS[token]
			field[name] = value
	if fieldtype in ("Section Break", "Column Break", "Tab Break") and "label" not in field:
		pass
	return field


def scrub(name):
	return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def perms(roles, submittable=False, single=False):
	out = []
	for role, level in roles:
		row = {
			"role": role,
			"read": 1,
			"report": 0 if single else 1,
			"export": 0 if single else 1,
			"print": 1,
			"email": 1,
			"share": 1,
		}
		if level in ("write", "full"):
			row.update({"write": 1, "create": 1})
		if level == "full":
			row.update({"delete": 0 if single else 1})
			if submittable:
				row.update({"submit": 1, "cancel": 1, "amend": 1})
		elif level == "write" and submittable:
			row.update({"submit": 1})
		out.append(row)
	return out


DEFAULT_ROLES = [
	("System Manager", "full"),
	("EXIM Manager", "full"),
	("EXIM User", "write"),
	("Accounts User", "read"),
]


def doctype(
	name,
	module,
	fields,
	*,
	autoname=None,
	naming_rule=None,
	istable=False,
	issingle=False,
	is_submittable=False,
	title_field=None,
	search_fields=None,
	roles=None,
	track_changes=True,
	sort_field="creation",
	quick_entry=False,
	editable_grid=True,
	links=None,
	extra=None,
	controller=None,
	is_tree=False,
	image_field=None,
):
	module_dir = APP_ROOT / scrub(module)
	folder = module_dir / "doctype" / scrub(name)
	folder.mkdir(parents=True, exist_ok=True)
	(module_dir / "doctype" / "__init__.py").touch()
	(folder / "__init__.py").touch()

	parsed = [parse_field(f) for f in fields]
	if is_submittable and not any(f["fieldname"] == "amended_from" for f in parsed):
		parsed.append(
			{
				"fieldname": "amended_from",
				"fieldtype": "Link",
				"label": "Amended From",
				"no_copy": 1,
				"options": name,
				"print_hide": 1,
				"read_only": 1,
				"search_index": 1,
			}
		)
	data = {
		"actions": [],
		"allow_rename": 0,
		"creation": TS,
		"doctype": "DocType",
		"engine": "InnoDB",
		"field_order": [f["fieldname"] for f in parsed],
		"fields": parsed,
		"links": links or [],
		"modified": TS,
		"modified_by": "Administrator",
		"module": module,
		"name": name,
		"owner": "Administrator",
		"permissions": [] if istable else perms(roles or DEFAULT_ROLES, is_submittable, issingle),
		"sort_field": sort_field,
		"sort_order": "DESC",
		"states": [],
	}
	if editable_grid:
		data["editable_grid"] = 1
	if istable:
		data["istable"] = 1
	if issingle:
		data["issingle"] = 1
	if is_submittable:
		data["is_submittable"] = 1
	if autoname:
		data["autoname"] = autoname
	if naming_rule:
		data["naming_rule"] = naming_rule
	if title_field:
		data["title_field"] = title_field
		data["show_title_field_in_link"] = 1
	if search_fields:
		data["search_fields"] = search_fields
	if track_changes and not istable:
		data["track_changes"] = 1
	if quick_entry:
		data["quick_entry"] = 1
	if is_tree:
		data["is_tree"] = 1
	if image_field:
		data["image_field"] = image_field
	if extra:
		data.update(extra)

	(folder / f"{scrub(name)}.json").write_text(json.dumps(data, indent=1, sort_keys=True) + "\n")
	py = folder / f"{scrub(name)}.py"
	if not py.exists():
		class_name = name.replace(" ", "").replace("-", "")
		body = controller or "\tpass\n"
		py.write_text(
			"# Copyright (c) 2026, Yasir Shaikh and contributors\n"
			"# For license information, please see license.txt\n\n"
			"from frappe.model.document import Document\n\n\n"
			f"class {class_name}(Document):\n{body}"
		)
	return folder
