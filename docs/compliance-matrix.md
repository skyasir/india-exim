# Compliance matrix

Each row maps a legal or regulatory requirement to the India EXIM feature that handles it and the scenario that tests it. It covers Phase 1 (exports and imports of goods) and, from Phase 2, Advance Authorisation, EPCG and rules of origin under trade agreements. Trade finance, SEZ/EOU and portal integrations come later.

> This is a working map for implementation, not legal advice. Rates, periods and forms change by notification; India EXIM keeps them as dated data or settings so they can be updated without code. Have a CA or customs broker review the setup for each client.

Status: **Done** = built and covered by automated tests. **Data** = the app holds the dated values; the client enters the current notified figures.

## Customs Act 1962, Customs Tariff Act 1975, Customs Valuation Rules 2007

| Requirement | Feature | Where | Status |
|---|---|---|---|
| Shipping bill for every export, with port, AD code and IEC | Shipping Bill, port picked from the Port Master (customs port list pre-loaded), AD code picked by port | Shipping Bill, Port Master (AD codes per port), Company > Export & Import | Done |
| Export value on FOB basis (CIF/CFR invoices less freight and insurance) | FOB worked out per line from the Incoterm; freight and insurance spread by value | Shipping Bill | Done |
| Customs exchange rate notified by CBIC for the date of the shipping bill / bill of entry | Dated export and import rates; picked by document date | Customs Exchange Rate | Data |
| ITC-HS classification of goods | 8-digit tariff item on Item, carried to every document and print | Customs Tariff Item, Item | Data |
| Quantity in the tariff's unit (UQC) on the shipping bill; per-unit incentive caps on that quantity | UQC and conversion from the stock unit kept on the item; shipping bill lines filled from it | Item > Export & Import, Shipping Bill | Done |
| Assessable value and duty on imports (BCD, SWS, AIDC, other duties) by tariff and date | Duty breakup on India Compliance's Bill of Entry, rates by date | Bill of Entry > EXIM fields, Customs Tariff Rate | Done |
| Let Export Order, EGM | LEO and EGM dates and status on the shipping bill | Shipping Bill | Done |
| Landed cost of imports | Landed Cost Voucher from the Bill of Entry (customs duty into stock value) | Bill of Entry, Landed Cost Voucher | Done |
| Duty Drawback (Section 75, Drawback Rules 2017) at All Industry Rates with caps | All Industry Rates (77/2023 as amended by 33/2024, jewellery left out) and RoSCTL schedules loaded by serial number; per-unit cap in the schedule's unit, brand rate per item, accrued at LEO, claim / scroll / receipt; the item says which schedule entry applies and whether drawback and RoDTEP are claimed | Export Incentive Rate, Item > Export & Import, Shipping Bill, Export Incentive Claim | Done |
| Records for post-clearance audit | Evidence pack: every document as PDF, attachments, payments, journals and change history in one ZIP | Shipping Bill / Bill of Entry > View > Evidence Pack | Done |

## Foreign Trade Policy 2023 and Handbook of Procedures (DGFT)

| Requirement | Feature | Where | Status |
|---|---|---|---|
| IEC, RCMC and status holder details | Registration fields; RCMC expiry tracked | Company > Export & Import | Done |
| Export policy of goods (Free / Restricted / Prohibited / STE), SCOMET | Policy and SCOMET flag on the tariff item; pre-shipment check on quotations, orders and invoices | Customs Tariff Item, India EXIM Settings > Pre-shipment Controls | Done |
| RoDTEP rates and e-scrips | RoDTEP rate by tariff and date with cap (or fixed amount per unit), loaded from Appendix 4R as published; accrual at LEO, e-scrip ledger, scrip used against import duty | Export Incentive Rate (tariff data: RoDTEP Appendix 4R), RoDTEP Scrip, Bill of Entry | Done |
| Incentive only on realised exports; recovery when proceeds are reduced or written off | Proportionate reversal for credit notes after shipment and write-offs, posted to Export Incentive Recovery | Shipping Bill (Drawback / RoDTEP Reversed) | Done |
| Merchant exporter buying at concessional GST, export within 90 days | Purchase flag, export-by date, shipping bill link, proof to supplier, alert and register | Purchase Invoice, Merchant Export Register | Done |

## Foreign Trade Policy 2023, Chapters 4 and 5: Advance Authorisation and EPCG

| Requirement | Feature | Where | Status |
|---|---|---|---|
| Duty-free import of inputs (AA) or capital goods (EPCG) against an authorisation, within its import validity | Authorisation with the imports allowed (ITC-HS, quantity, CIF); Bill of Entry under it records basic customs duty as foregone, checks the validity and the quantity left | Export Authorisation, Bill of Entry > Import Under Authorisation | Done |
| Export obligation within the EO period (AA: products and FOB; EPCG: a multiple of duty and taxes saved, with block-wise targets) | EO worked out per scheme, credited from shipping bills naming the authorisation, % fulfilled, status, alerts 60 days before the EO period ends | Export Authorisation, Shipping Bill > Export Under Authorisation, Authorisation Register | Done |
| Incentives on exports discharging an obligation only where admissible | Drawback / RoDTEP admissible ticks on each authorisation, applied to its shipping bills | Export Authorisation | Done |
| Redemption (EODC) or regularisation | EODC / regularisation fields set the status | Export Authorisation | Done |

## Trade agreements: rules of origin, CAROTAR 2020 (Customs Tariff Act s. 28DA)

| Requirement | Feature | Where | Status |
|---|---|---|---|
| Agreements in force, partner countries, tariff and rules of origin notifications | India's FTAs / CEPAs / CECAs loaded with partner countries, in-force date and general origin criterion; notifications and RVC % kept as data | Trade Agreement | Data |
| Preferential Certificate of Origin for exports under an agreement (DGFT Common Digital Platform) | Certificate of Origin from a shipping bill or export invoice; destination checked against the partner countries; application, issue, validity and rejection | Certificate of Origin | Done |
| Origin criterion met: wholly obtained, RVC, change in tariff heading / sub-heading, product-specific rule | RVC = (FOB - non-originating materials) / FOB from the default BOM and each material's country of origin (partner-country materials count as originating); CTH / CTSH against the materials' ITC-HS codes; PSR confirmed by the user | Certificate of Origin > Goods | Done |
| Non-preferential certificate of origin (Chamber of Commerce) | Certificate type Non-Preferential | Certificate of Origin | Done |
| Concessional duty on imports only for goods of a partner country, with a valid certificate of origin | Bill of Entry claims an agreement: country of origin checked, CoO number and date required, CoO validity checked, preferential rate used from the tariff item | Bill of Entry > Trade Agreement, Customs Tariff Item > Preferential Rate Under | Done |
| Importer holds origin-related information (CAROTAR 2020, Form I) | Confirmation needed before the Bill of Entry is submitted | Bill of Entry | Done |
| Duty forgone under agreements | Duty saved per item and per Bill of Entry against the standard rate; number card | Bill of Entry, Trade Agreements page | Done |

## FEMA 1999, RBI Master Direction on Export of Goods and Services

| Requirement | Feature | Where | Status |
|---|---|---|---|
| Realise export proceeds within the period RBI allows: 9 months, 15 months for exports from 14.11.2025 (FEM (Export of Goods and Services) (Second Amendment) Regulations, 2025) | Dated RBI periods; each shipping bill takes the period in force on its date; realisation status from ordinary payments and credit notes; ageing report; alerts before and after the due date | India EXIM Settings > FEMA / RBI, Shipping Bill, Export Realisation Ageing, notifications | Done |
| EDPMS: shipping bills outstanding with the AD bank | Outstanding per shipping bill, by AD code | Export Realisation Ageing, Shipping Bill Register | Done |
| Extension and write-off of unrealised proceeds (AD bank / RBI / self) | Realisation actions with approving authority and reference; incentives reversed on write-off | Shipping Bill > Realisation Actions | Done |
| Agency commission to overseas agents | Commission recorded on the shipping bill, not counted as unrealised | Shipping Bill > Overseas Agent / Agency Commission | Done |
| Advance against exports: ship within the period RBI allows (1 year; 3 years for advances from 14.11.2025) | Dated RBI periods by advance date; advance register from payment entries; alerts at 30 days and when overdue | India EXIM Settings > FEMA / RBI, Export Advance Register, daily alert | Done |
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
| Shipping instructions, cut-offs, dangerous goods and reefer details | Shipment with booking, cut-offs, DG/UN number, reefer temperature (filled from the items' DG class, UN number and temperature); shipping instructions print | Export Shipment, Item > Export & Import, Shipping Instructions | Done |

## Destination-country and buyer requirements

| Requirement | Feature | Where | Status |
|---|---|---|---|
| Documents each destination, product, Incoterm, payment term and buyer requires | Rule-based checklist merged per shipment, plus the documents set on each item; readiness %; optional gate; due-date alerts | Document Requirement Template, Item > Export & Import, Export Shipment | Done |
| Sanctioned or high-risk destinations; denied-party screening of buyers | Country risk flags; buyer screening date and result; ECGC buyer limit; checks on export orders | Country > Export Controls, Customer > Export Details | Done |

## Go-live and audit

| Requirement | Feature | Where | Status |
|---|---|---|---|
| Bring in open shipping bills, scrips, rates and LUT at go-live | Data Import templates; opening shipping bills without a duplicate accrual | `india_exim/setup/import_templates` | Done |
| Year-end: unrealised exports, incentives receivable, refunds pending | Registers and ageing reports with summaries | Reports | Done |
