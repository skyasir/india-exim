<img src="assets/icon.svg" width="64" height="64" alt="">

# India EXIM

Export–import compliance for Indian businesses on ERPNext v16, built on top of
[India Compliance](https://github.com/resilient-tech/india-compliance) (which keeps owning GST).

**Phase 1 (in progress)**

- Foreign-trade masters: ITC-HS tariff with dated duty rates, RoDTEP / Drawback rates with per-unit caps,
  CBIC customs exchange rates, Letter of Undertaking, AD code registrations, default EXIM accounts on Company.
- Exports: Export Shipment (route, cut-offs, containers, charges), Shipping Bill (FOB from Incoterm, customs
  exchange rate, incentives at LEO-date rates, accrual on LEO, realisation due date).
- Trade documents: country / country-group / product / Incoterm / payment-term / buyer rules merged into a
  per-shipment checklist, with due dates, readiness % and an optional block before documents go out.
- LUT check on zero-rated export invoices.

Law is stored as dated data (rate tables with effective dates and notification numbers), never hard-coded.
Rates shipped in tests are illustrative only — always load the notified schedules for real use.

## Install

```bash
bench get-app https://github.com/resilient-tech/india-compliance --branch version-16
bench get-app <this repository>
bench --site <site> install-app india_exim
```

## Tests

```bash
bench --site <test-site> set-config allow_tests true
bench --site <test-site> run-tests --app india_exim
```

## License

GNU GPL v3
