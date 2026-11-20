# Generators

India EXIM's standard records (navigation, dashboards, print formats, reports, onboarding and some
DocType JSON) are written by these scripts, so they stay consistent. Edit the script, run it from
this folder, then `bench migrate`.

| Script | Writes |
|---|---|
| `nav_gen.py` | One Sidebar per module and the app Dock. Set `BENCH_APPS` to a bench's `apps` folder so links to ERPNext / India Compliance doctypes and reports can be checked. |
| `dash_gen.py` | Number cards, dashboard charts, the India EXIM dashboard, the home workspace and one overview workspace per module |
| `print_gen.py` | Print format JSON from each format's `.html` template |
| `report_gen.py` | Report JSON and `__init__.py` for script reports (the `.py` and `.js` are hand-written) |
| `onboarding_gen.py` | Onboarding steps and the India EXIM module onboarding |
| `doctype_gen.py` + `specs_*.py` | DocType JSON from compact field specs (`python specs_exports.py` etc.); existing controllers are never overwritten |

Frappe only re-imports a standard record when its `modified` timestamp changes, so bump `TS` in a
script after changing it.
