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

## Tariff data (`data/`)

Converters that turn the published DGFT / CBIC schedules into India EXIM's tariff data packs in
`india_exim/setup/data/tariff`. The source PDFs are not kept in the repo; download them from the
DGFT / CBIC site named in each script. Every row carries its effective dates.

| Script | Source | Writes |
|---|---|---|
| `data/rodtep_4r.py` | Appendix 4R w.e.f. 10.10.2024 and the changes w.e.f. 01.05.2026 (DGFT > Regulations > RoDTEP) | `rodtep_4r.csv` |
| `data/drawback_air.py` | Notification 77/2023-Customs (N.T.), with 33/2024 transcribed in the script | `drawback_air.csv` |
| `data/rosctl.py` | Ministry of Textiles notification 14/26/2016-IT (Vol.II), 08.03.2019 | `rosctl.csv` |

After a new notification: run the converter, check the counts it prints against the notification,
bump the pack's `version` in `india_exim/setup/tariff_data.py` and migrate. Sites load the new
version once; rates a user entered by hand are kept.
