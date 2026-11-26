from doctype_gen import doctype

DOCS = "Trade Documents"
MODES = "\\nSea FCL\\nSea LCL\\nAir\\nCourier\\nRoad\\nRail"
PAYMENT_TERMS = "\\nAdvance\\nLetter of Credit\\nDocuments against Payment (DP)\\nDocuments against Acceptance (DA)\\nOpen Account"

doctype(
	"Document Requirement Template",
	DOCS,
	[
		"template_name:Data:Rule Name|reqd|unique|list",
		"direction:Select:Applies To|opt=Export\\nImport|default=Export|reqd|list|filter",
		"enabled:Check:Enabled|default=1",
		"column_break_head:Column Break",
		"is_statutory:Check:Indian Statutory Set|desc=Applies to every shipment in this direction, before any country or buyer rule.",
		"match_section:Section Break:Applies When|desc=Leave a condition empty to match any value. The more conditions a rule has, the higher its priority when two rules ask for the same document.",
		"for_country:Link:Country|opt=Country|list|filter|depends=eval:!doc.is_statutory",
		"for_country_group:Link:Country Group|opt=Country Group|list|filter|depends=eval:!doc.is_statutory",
		"for_tariff_prefixes:Data:Tariff Chapters / Prefixes|depends=eval:!doc.is_statutory|desc=Comma-separated ITC-HS prefixes, e.g. 09, 1006, 52",
		"for_item_group:Link:Item Group|opt=Item Group|depends=eval:!doc.is_statutory",
		"column_break_match:Column Break",
		"for_incoterm:Link:Incoterm|opt=Incoterm|depends=eval:!doc.is_statutory",
		"for_payment_terms_type:Select:Payment Terms|opt="
		+ PAYMENT_TERMS
		+ "|depends=eval:!doc.is_statutory",
		"for_mode_of_transport:Select:Mode|opt=" + MODES + "|depends=eval:!doc.is_statutory",
		"for_customer:Link:Customer|opt=Customer|depends=eval:!doc.is_statutory && doc.direction=='Export'",
		"for_supplier:Link:Supplier|opt=Supplier|depends=eval:!doc.is_statutory && doc.direction=='Import'",
		"requirements_section:Section Break:Required Documents",
		"requirements:Table:Documents|opt=Document Requirement|reqd",
	],
	autoname="field:template_name",
	naming_rule="By fieldname",
	search_fields="direction,for_country,for_country_group",
	roles=[("System Manager", "full"), ("EXIM Manager", "full"), ("EXIM User", "read")],
	extra={"creation": "2026-11-19 19:00:00.000000", "modified": "2026-11-26 22:00:00.000000"},
)

doctype(
	"Document Requirement",
	DOCS,
	[
		"document_type:Link:Document|opt=Trade Document Type|reqd|list|width=3",
		"mandatory:Check:Mandatory|default=1|list|width=1",
		"stage:Select:Stage|opt=Order\\nPre-shipment\\nAt Shipment\\nPost-shipment|default=Pre-shipment|list|width=1",
		"due_event:Select:Due Relative To|opt=\\nOrder Date\\nETD\\nBL Date\\nETA|list|width=1",
		"due_offset_days:Int:Offset (Days)|list|width=1|desc=Negative = before the event, e.g. -5 for five days before ETD.",
		"responsible:Link:Responsible|opt=User|width=1",
		"instructions:Small Text:Instructions",
	],
	istable=True,
)
