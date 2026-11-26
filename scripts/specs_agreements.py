"""Certificates of Origin for exports under trade agreements (FTA / CEPA / CECA) and for proof of origin."""

from doctype_gen import doctype

AGREEMENTS = "Trade Agreements"
INR = "Company:company:default_currency"
CRITERIA = "\\nWO\\nRVC\\nCTH\\nCTSH\\nRVC + CTH\\nRVC + CTSH\\nRVC or CTH\\nPSR"
# the same list as india_exim.trade_agreements.AGREEMENTS (used on the Bill of Entry)
AGREEMENT_OPTIONS = (
	"\\nIndia-UAE CEPA\\nASEAN-India FTA (AIFTA)\\nIndia-Korea CEPA\\nIndia-Japan CEPA\\nIndia-Malaysia CECA"
	"\\nIndia-Singapore CECA\\nIndia-Australia ECTA\\nIndia-Mauritius CECPA\\nIndia-EFTA TEPA\\nSAFTA"
	"\\nIndia-Sri Lanka FTA (ISFTA)\\nAPTA\\nOther"
)
CRITERIA_HELP = (
	"As asked on the certificate application. WO: wholly obtained or produced in India. RVC: regional value"
	" content, worked out here; compare it with the agreement's minimum. CTH / CTSH: every imported"
	" material is under a different 4-digit heading / 6-digit sub-heading from the product. PSR: the"
	" product-specific rule in the agreement's annex."
)

doctype(
	"Certificate of Origin Item",
	AGREEMENTS,
	[
		"item_code:Link:Item|opt=Item|reqd|list|width=2",
		"item_name:Data:Item Name|fetch=item_code.item_name",
		"customs_tariff_item:Link:ITC-HS|opt=Customs Tariff Item|list|width=1|fetch=item_code.exim_customs_tariff_item|if_empty=1",
		"qty:Float:Qty|list|width=1",
		"uom:Link:UOM|opt=UOM",
		"shipping_bill_item:Data:Shipping Bill Item|hidden|nocopy",
		"column_break_values:Column Break",
		"fob_value:Currency:FOB Value (INR)|opt=" + INR + "|list|width=1",
		"non_originating_value:Currency:Non-originating Materials (INR)|opt="
		+ INR
		+ "|ro_depends=eval:!doc.manual_values",
		"rvc_percent:Percent:RVC %|ro|list|width=1",
		"manual_values:Check:Values Entered Manually|desc=Tick to enter the FOB and non-originating values yourself instead of taking them from the shipping bill and the default BOM.",
		"criterion_section:Section Break:Origin",
		"origin_criterion:Select:Origin Criterion|opt=" + CRITERIA + "|list|width=1|desc=" + CRITERIA_HELP,
		"column_break_criterion:Column Break",
		"origin_note:Small Text:How the RVC Was Worked Out|ro",
	],
	istable=True,
)

doctype(
	"Certificate of Origin",
	AGREEMENTS,
	[
		"naming_series:Select:Series|opt=COO-.YYYY.-.#####|reqd|default=COO-.YYYY.-.#####|phide",
		"certificate_type:Select:Type|opt=Preferential\\nNon-Preferential|default=Preferential|reqd|list|filter|desc=Preferential: under a trade agreement, so the buyer pays less duty. Non-preferential: proof of Indian origin only, usually from a Chamber of Commerce.",
		"trade_agreement:Select:Trade Agreement|opt="
		+ AGREEMENT_OPTIONS
		+ "|list|filter|depends=eval:doc.certificate_type == 'Preferential'|mandatory_depends=eval:doc.certificate_type == 'Preferential'",
		"company:Link:Company|opt=Company|reqd|filter",
		"shipping_bill:Link:Shipping Bill|opt=Shipping Bill|search|desc=Items, buyer and destination are taken from it.",
		"sales_invoice:Link:Export Invoice|opt=Sales Invoice|desc=When there is no shipping bill yet.",
		"export_shipment:Link:Export Shipment|opt=Export Shipment|desc=Its document checklist is ticked when the certificate is issued.",
		"column_break_head:Column Break",
		"status:Select:Status|opt=Draft\\nApplied\\nIssued\\nRejected|default=Draft|ro|list|filter|bold|nocopy",
		"customer:Link:Buyer|opt=Customer|reqd|filter",
		"customer_name:Data:Buyer Name|fetch=customer.customer_name",
		"destination_country:Link:Destination Country|opt=Country|reqd|list|filter",
		"application_section:Section Break:Application",
		"issuing_agency:Select:Issuing Agency|opt=\\nExport Inspection Council (EIC)\\nFIEO\\nExport Promotion Council\\nChamber of Commerce\\nOther",
		"application_number:Data:Application No.|search|nocopy|desc=Reference on the DGFT Common Digital Platform for Certificate of Origin.",
		"application_date:Date:Application Date|nocopy",
		"column_break_application:Column Break",
		"certificate_number:Data:Certificate No.|list|search|nocopy",
		"certificate_date:Date:Certificate Date|nocopy",
		"valid_upto:Date:Valid Upto|ro|nocopy",
		"is_rejected:Check:Rejected|nocopy",
		"rejection_reason:Small Text:Reason|depends=is_rejected|mandatory_depends=is_rejected|nocopy",
		"items_section:Section Break:Goods|desc=RVC = (FOB value - value of non-originating materials) / FOB value x 100. Non-originating materials come from the item's default BOM: materials whose Country of Origin is set and is not India. Correct the values when the BOM differs from what was made, or when materials from the partner country count as originating under the agreement.",
		"items:Table:Items|opt=Certificate of Origin Item|reqd",
		"totals_section:Section Break:Totals",
		"total_fob_value:Currency:Total FOB Value (INR)|opt=" + INR + "|ro",
		"column_break_totals:Column Break",
		"remarks:Small Text:Remarks",
	],
	autoname="naming_series:",
	title_field="customer_name",
	search_fields="customer_name,trade_agreement,certificate_number",
	roles=[
		("System Manager", "full"),
		("EXIM Manager", "full"),
		("EXIM User", "write"),
		("Sales User", "write"),
		("Accounts User", "read"),
		("Auditor", "read"),
	],
	extra={"modified": "2026-11-26 20:00:00.000000"},
)
