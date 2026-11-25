from doctype_gen import doctype

EXPORTS = "Exports"
ROLES = [
	("System Manager", "full"),
	("EXIM Manager", "full"),
	("EXIM User", "full"),
	("Sales Manager", "full"),
	("Sales User", "write"),
	("Accounts User", "read"),
]
INR = "Company:company:default_currency"

doctype(
	"Export Costing Item",
	EXPORTS,
	[
		"item_code:Link:Item|opt=Item|reqd|list|width=2",
		"item_name:Data:Item Name|fetch=item_code.item_name|ro",
		"customs_tariff_item:Link:ITC-HS|opt=Customs Tariff Item|fetch=item_code.exim_customs_tariff_item|ro",
		"qty:Float:Qty|reqd|list|default=1|width=1",
		"uom:Link:UOM|opt=UOM|fetch=item_code.stock_uom|list|width=1",
		"ex_works_cost:Currency:Ex-works Cost / Unit (INR)|opt="
		+ INR
		+ "|reqd|list|width=2|desc=Cost of goods at the factory gate, including your overheads.",
		"column_break_rates:Column Break",
		"drawback_rate:Percent:Drawback %|desc=Fetched from Export Incentive Rate for the ITC-HS code; per-unit caps are not applied here.",
		"rodtep_rate:Percent:RoDTEP %",
		"rosctl_rate:Percent:RoSCTL % (State + Central)",
		"costs_section:Section Break:Build-up (INR)",
		"exw_amount:Currency:EXW|opt=" + INR + "|ro",
		"fob_amount:Currency:FOB|opt=" + INR + "|ro",
		"column_break_build:Column Break",
		"cost_at_basis:Currency:Cost at Incoterm|opt=" + INR + "|ro",
		"incentive_amount:Currency:Incentives|opt=" + INR + "|ro",
		"price_section:Section Break:Price",
		"price_inr:Currency:Price (INR)|opt=" + INR + "|ro",
		"column_break_price:Column Break",
		"rate_fc:Currency:Rate / Unit|opt=currency|ro|list|width=2",
		"amount_fc:Currency:Amount|opt=currency|ro",
		"currency:Link:Currency|opt=Currency|hidden|ro",
	],
	istable=True,
)

doctype(
	"Export Costing Sheet",
	EXPORTS,
	[
		"naming_series:Select:Series|opt=ECS-.YYYY.-.#####|reqd|default=ECS-.YYYY.-.#####|phide",
		"company:Link:Company|opt=Company|reqd",
		"customer:Link:Customer|opt=Customer|list|filter",
		"quotation:Link:Quotation|opt=Quotation|list|filter|desc=Rates can be copied into this quotation while it is a draft.",
		"column_break_head:Column Break",
		"posting_date:Date:Date|reqd|default=Today",
		"destination_country:Link:Destination Country|opt=Country",
		"incoterm:Link:Incoterm (Price Basis)|opt=Incoterm|reqd|default=FOB",
		"currency:Link:Quote Currency|opt=Currency|reqd",
		"exchange_rate:Float:Exchange Rate (INR per unit)|reqd|precision=4|desc=Use a forward rate if one is booked.",
		"items_section:Section Break:Goods",
		"items:Table:Items|opt=Export Costing Item|reqd",
		"fob_costs_section:Section Break:Costs up to FOB (INR, for the whole shipment)",
		"packing:Currency:Export Packing|opt=" + INR,
		"inland_haulage:Currency:Inland Haulage to Port|opt=" + INR,
		"column_break_fob:Column Break",
		"port_charges:Currency:CHA, THC and Port Charges|opt=" + INR,
		"other_fob_costs:Currency:Other Costs (inspection, certificates)|opt=" + INR,
		"main_carriage_section:Section Break:Main Carriage (INR)",
		"freight:Currency:Ocean / Air Freight|opt="
		+ INR
		+ "|desc=Counted in the price for CFR, CPT, CIF, CIP and D-terms.",
		"column_break_carriage:Column Break",
		"insurance:Currency:Marine Insurance|opt="
		+ INR
		+ "|desc=Counted in the price for CIF, CIP and D-terms.",
		"percentages_section:Section Break:Charges on the Price and Margin",
		"bank_charges_percent:Percent:Bank Charges %|default=0.25",
		"ecgc_premium_percent:Percent:ECGC Premium %",
		"column_break_pct:Column Break",
		"margin_percent:Percent:Target Margin %|reqd|default=10",
		"include_incentives:Check:Pass Incentives to the Buyer|default=1|desc=Lower the price by the Drawback and RoDTEP expected on the FOB value.",
		"results_section:Section Break:Result",
		"total_exw:Currency:EXW Total|opt=" + INR + "|ro",
		"total_fob_cost:Currency:FOB Cost|opt=" + INR + "|ro",
		"total_cost_at_basis:Currency:Cost at Incoterm|opt=" + INR + "|ro",
		"total_incentives:Currency:Incentives Expected|opt=" + INR + "|ro",
		"column_break_results:Column Break",
		"total_price_inr:Currency:Price (INR)|opt=" + INR + "|ro|bold",
		"total_price_fc:Currency:Price|opt=currency|ro|bold|list",
		"margin_amount:Currency:Margin (INR)|opt=" + INR + "|ro",
		"remarks:Small Text:Remarks",
	],
	autoname="naming_series:",
	title_field="customer",
	roles=ROLES,
	search_fields="customer,quotation",
)
