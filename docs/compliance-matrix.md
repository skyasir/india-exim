# Compliance matrix

Each row maps a legal or regulatory requirement to the India EXIM feature that handles it and the scenario that tests it. It covers Phase 1 (exports and imports of goods). Licences (Advance Authorisation, EPCG), FTA rules of origin, trade finance, SEZ/EOU and portal integrations come in later phases.

> This is a working map for implementation, not legal advice. Rates, periods and forms change by notification; India EXIM keeps them as dated data or settings so they can be updated without code. Have a CA or customs broker review the setup for each client.

Status: **Done** = built and covered by automated tests. **Data** = the app holds the dated values; the client enters the current notified figures.

## Customs Act 1962, Customs Tariff Act 1975, Customs Valuation Rules 2007

| Requirement | Feature | Where | Status |
|---|---|---|---|
| Shipping bill for every export, with port, AD code and IEC | Shipping Bill, port code validated against the customs port list, AD code picked by port | Shipping Bill, AD Code Registration, Company > Export & Import | Done |
| Export value on FOB basis (CIF/CFR invoices less freight and insurance) | FOB worked out per line from the Incoterm; freight and insurance spread by value | Shipping Bill | Done |
| Customs exchange rate notified by CBIC for the date of the shipping bill / bill of entry | Dated export and import rates; picked by document date | Customs Exchange Rate | Data |
| ITC-HS classification of goods | 8-digit tariff item on Item, carried to every document and print | Customs Tariff Item, Item | Data |
| Assessable value and duty on imports (BCD, SWS, AIDC, other duties) by tariff and date | Duty breakup on India Compliance's Bill of Entry, rates by date | Bill of Entry > EXIM fields, Customs Tariff Rate | Done |
| Let Export Order, EGM | LEO and EGM dates and status on the shipping bill | Shipping Bill | Done |
| Landed cost of imports | Landed Cost Voucher from the Bill of Entry (customs duty into stock value) | Bill of Entry, Landed Cost Voucher | Done |
| Duty Drawback (Section 75, Drawback Rules 2017) at All Industry Rates with caps | Drawback rate by tariff and date, per-unit cap, accrued at LEO, claim / scroll / receipt | Export Incentive Rate, Shipping Bill, Export Incentive Claim | Done |
| Records for post-clearance audit | Evidence pack: every document as PDF, attachments, payments, journals and change history in one ZIP | Shipping Bill / Bill of Entry > View > Evidence Pack | Done |

## Foreign Trade Policy 2023 and Handbook of Procedures (DGFT)

| Requirement | Feature | Where | Status |
|---|---|---|---|
| IEC, RCMC and status holder details | Registration fields; RCMC expiry tracked | Company > Export & Import | Done |
| Export policy of goods (Free / Restricted / Prohibited / STE), SCOMET | Policy and SCOMET flag on the tariff item; pre-shipment check on quotations, orders and invoices | Customs Tariff Item, India EXIM Settings > Pre-shipment Controls | Done |
| RoDTEP rates and e-scrips | RoDTEP rate by tariff and date with cap, accrual at LEO, e-scrip ledger, scrip used against import duty | Export Incentive Rate, RoDTEP Scrip, Bill of Entry | Done |
| Incentive only on realised exports; recovery when proceeds are reduced or written off | Proportionate reversal for credit notes after shipment and write-offs, posted to Export Incentive Recovery | Shipping Bill (Drawback / RoDTEP Reversed) | Done |
| Merchant exporter buying at concessional GST, export within 90 days | Purchase flag, export-by date, shipping bill link, proof to supplier, alert and register | Purchase Invoice, Merchant Export Register | Done |

## FEMA 1999, RBI Master Direction on Export of Goods and Services

| Requirement | Feature | Where | Status |
|---|---|---|---|
| Realise export proceeds within the period RBI allows (a setting, so a change in the period is a settings change) | Realisation due date and status from ordinary payments and credit notes; ageing report; alerts before and after the due date | Shipping Bill, Export Realisation Ageing, notifications | Done |
| EDPMS: shipping bills outstanding with the AD bank | Outstanding per shipping bill, by AD code | Export Realisation Ageing, Shipping Bill Register | Done |
| Extension and write-off of unrealised proceeds (AD bank / RBI / self) | Realisation actions with approving authority and reference; incentives reversed on write-off | Shipping Bill > Realisation Actions | Done |
| Agency commission to overseas agents | Commission recorded on the shipping bill, not counted as unrealised | Shipping Bill > Overseas Agent / Agency Commission | Done |
| Advance against exports: ship within the period RBI allows (a setting) | Advance register from payment entries; alerts at 30 days and when overdue | Export Advance Register, daily alert | Done |
| Free of cost / sample exports need no realisation | Export type "Free of Cost / Sample" | Shipping Bill | Done |
| Inward remittance reference (IRM / FIRC), purpose code | Fields on Payment Entry | Payment Entry > Foreign Remittance | Done |
| Documents to AD bank for collection / negotiation | Bank covering letter, bill of exchange, beneficiary certificate | Print formats | Done |

## RBI Master Direction on Import of Goods and Services

| Requirement | Feature | Where | Status |
|---|---|---|---|
| Import payment within the period; IDPMS | Payment status per Bill of Entry from ordinary payments; ageing; due alert | Bill of Entry, Import Payment Ageing | Done |
| Form 15CA / 15CB for outward remittances | Acknowledgement and reference on the payment | Payment Entry > Foreign Remittance | Done |

## CGST / IGST Acts (exports as zero-rated supply)

| Requirement | Feature | Where | Status |
|---|---|---|---|
| Export without IGST only under a valid LUT (RFD-11) | LUT with validity; zero-rated invoices checked (block / warn / off) and linked to the LUT | Letter of Undertaking, Sales Invoice, LUT Register | Done |
| Invoice declaration: "supply meant for export under LUT / on payment of IGST" | Printed on the export invoice with the LUT ARN | Export Commercial Invoice | Done |
| Shipping bill details in GSTR-1 (Table 6A) | Shipping bill number, date and port written back to India Compliance's invoice fields | Shipping Bill > Sales Invoice | Done |
| Refund of IGST paid on exports / of unutilised ITC | Refund claim tracking: application, sanction, receipt and accounting | GST Refund Claim | Done |
| Customs duty and IGST on imports for ITC | Duty fed into India Compliance's Bill of Entry so its IGST and ITC logic runs unchanged | Bill of Entry | Done |

## SOLAS (Chapter VI, Regulation 2) and carriage

| Requirement | Feature | Where | Status |
|---|---|---|---|
| Verified Gross Mass per container before loading | VGM on each container; VGM declaration print; VGM cut-off | Export Shipment, VGM Declaration | Done |
| Shipping instructions, cut-offs, dangerous goods and reefer details | Shipment with booking, cut-offs, DG/UN number, reefer temperature; shipping instructions print | Export Shipment, Shipping Instructions | Done |

## Destination-country and buyer requirements

| Requirement | Feature | Where | Status |
|---|---|---|---|
| Documents each destination, product, Incoterm, payment term and buyer requires | Rule-based checklist merged per shipment; readiness %; optional gate; due-date alerts | Document Requirement Template, Export Shipment | Done |
| Sanctioned or high-risk destinations; denied-party screening of buyers | Country risk flags; buyer screening date and result; ECGC buyer limit; checks on export orders | Country > Export Controls, Customer > Export Details | Done |

## Go-live and audit

| Requirement | Feature | Where | Status |
|---|---|---|---|
| Bring in open shipping bills, scrips, rates and LUT at go-live | Data Import templates; opening shipping bills without a duplicate accrual | `india_exim/setup/import_templates` | Done |
| Year-end: unrealised exports, incentives receivable, refunds pending | Registers and ageing reports with summaries | Reports | Done |
