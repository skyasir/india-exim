# Go-live import templates

Blank templates for **Data Import** (Desk > Data Import > New, choose the DocType, "Insert New Records", attach the filled CSV). The headers match what Data Import expects; keep them as they are.

Load them in this order:

| Order | Template | What to enter |
|---|---|---|
| 1 | `customs_tariff_item.csv` | Each 8-digit ITC-HS code you trade, its export/import policy, and the duty rates (one row per rate, with the effective date and notification). |
| 2 | `export_incentive_rate.csv` | Drawback (AIR) and RoDTEP rates for those codes, with caps per unit. |
| 3 | `customs_exchange_rate.csv` | CBIC exchange rates from the start of the year (or at least the current fortnight). |
| 4 | `letter_of_undertaking.csv` | The current year's LUT. |
| 5 | `shipping_bill.csv` | Shipping bills from before go-live that still matter: awaiting realisation, incentives not yet claimed or received. Tick **Is Opening Entry**. |
| 6 | `rodtep_scrip.csv` | RoDTEP e-scrips in hand, with what has been used so far. |

## Opening shipping bills

1. Create the unpaid export invoices first with ERPNext's **Opening Invoice Creation Tool** (Accounts). India EXIM reads realisation from the payments against those invoices.
2. In `shipping_bill.csv`, put each opening invoice in the **Sales Invoice** column of its items, with the LEO date.
3. Tick **Is Opening Entry**. No accrual entry is posted for these: the drawback and RoDTEP still receivable should already be in the opening balances of the receivable accounts. They can be claimed with an Export Incentive Claim as usual.

Shipping bills that are fully realised and fully claimed do not need to be imported.
