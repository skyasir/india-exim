"""Trade agreements (FTA / CEPA / CECA): Certificates of Origin for exports, concessional duty for imports."""

from doctype_gen import doctype

AGREEMENTS = "Trade Agreements"
INR = "Company:company:default_currency"
CRITERIA = "\\nWO\\nRVC\\nCTH\\nCTSH\\nRVC + CTH\\nRVC + CTSH\\nRVC or CTH\\nPSR"
CRITERIA_HELP = (
	"WO: wholly obtained or produced in India. RVC: regional value content of at least the agreement's"
	" minimum. CTH / CTSH: every non-originating material is under a different 4-digit heading / 6-digit"
	" sub-heading from the product. PSR: the product-specific rule in the agreement's annex."
)

doctype(
	"Trade Agreement",
	AGREEMENTS,
	[
		"agreement_name:Data:Agreement|reqd|unique|list|bold|desc=As the trade knows it, e.g. India-UAE CEPA, AIFTA, SAFTA.",
		"agreement_type:Select:Type|opt=FTA\\nCEPA\\nCECA\\nECTA\\nTEPA\\nCECPA\\nPTA|default=FTA|list|filter",
		"in_force_from:Date:In Force From|list",
		"disabled:Check:Disabled",
		"column_break_head:Column Break",
		"partner_countries:Table MultiSelect:Partner Countries|opt=Country Group Member|reqd|desc=Goods from these countries can get the concessional duty in India, and Indian goods going there can get theirs.",
		"notifications_section:Section Break:Notifications",
		"tariff_notification:Data:Tariff Notification (Concessional Duty)|desc=Customs notification with the preferential rates, e.g. 22/2022-Customs for India-UAE CEPA.",
		"column_break_notifications:Column Break",
		"origin_notification:Data:Rules of Origin Notification|desc=Customs (N.T.) notification with the rules of origin, e.g. 39/2022-Customs (N.T.).",
		"origin_section:Section Break:General Rule of Origin|desc=" + CRITERIA_HELP,
		"origin_criterion:Select:Origin Criterion|opt="
		+ CRITERIA
		+ "|list|desc=The rule for products the agreement's product-specific rules do not cover.",
		"rvc_percent:Percent:Minimum RVC %|desc=Regional value content needed when the criterion includes RVC.",
		"column_break_origin:Column Break",
		"certificate_form:Data:Certificate of Origin Form|desc=e.g. Form AI (AIFTA). Applied for on the DGFT Common Digital Platform for Certificate of Origin.",
		"certificate_validity_months:Int:Certificate Valid For (Months)|default=12",
		"verify_note:Small Text:Source / Verification Note",
	],
	autoname="field:agreement_name",
	naming_rule="By fieldname",
	search_fields="agreement_type",
	roles=[
		("System Manager", "full"),
		("EXIM Manager", "full"),
		("EXIM User", "read"),
		("Sales User", "read"),
		("Purchase User", "read"),
		("Accounts User", "read"),
	],
	extra={"modified": "2026-11-26 18:00:00.000000"},
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
		"qualifies:Check:Meets the Rule of Origin|list|width=1|ro_depends=eval:doc.origin_criterion != 'PSR'|desc=Worked out from the criterion. For a product-specific rule, tick it once you have checked the rule.",
		"column_break_criterion:Column Break",
		"origin_note:Small Text:How It Was Worked Out|ro",
	],
	istable=True,
)

doctype(
	"Certificate of Origin",
	AGREEMENTS,
	[
		"naming_series:Select:Series|opt=COO-.YYYY.-.#####|reqd|default=COO-.YYYY.-.#####|phide",
		"certificate_type:Select:Type|opt=Preferential\\nNon-Preferential|default=Preferential|reqd|list|filter|desc=Preferential: under a trade agreement, so the buyer pays less duty. Non-preferential: proof of Indian origin only, usually from a Chamber of Commerce.",
		"trade_agreement:Link:Trade Agreement|opt=Trade Agreement|list|filter|depends=eval:doc.certificate_type == 'Preferential'|mandatory_depends=eval:doc.certificate_type == 'Preferential'",
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
		"items_section:Section Break:Goods|desc=RVC = (FOB value - value of non-originating materials) / FOB value x 100. Non-originating materials come from the item's default BOM: materials whose Country of Origin is set and is neither India nor a partner country. Correct the values when the BOM differs from what was made.",
		"items:Table:Items|opt=Certificate of Origin Item|reqd",
		"totals_section:Section Break:Totals",
		"total_fob_value:Currency:Total FOB Value (INR)|opt=" + INR + "|ro",
		"column_break_totals:Column Break",
		"all_items_qualify:Check:All Items Meet the Rule of Origin|ro",
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
	extra={"modified": "2026-11-26 18:00:00.000000"},
)
