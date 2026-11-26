"""Import Shipment: from booking abroad to clearance here."""

from doctype_gen import FOREIGN_PORTS, INDIAN_PORTS, doctype

IMPORTS = "Imports"
ROLES = [
	("System Manager", "full"),
	("EXIM Manager", "full"),
	("EXIM User", "full"),
	("Purchase User", "read"),
	("Accounts User", "read"),
	("Accounts Manager", "read"),
]
STATUSES = "Planned\\nBooked\\nShipped\\nArrived\\nCustoms Cleared\\nDelivered\\nClosed\\nCancelled"
MODES = "Sea FCL\\nSea LCL\\nAir\\nCourier\\nRoad\\nRail"
STAMP = {"creation": "2026-11-26 10:00:00.000000", "modified": "2026-11-26 10:00:00.000000"}

doctype(
	"Import Shipment",
	IMPORTS,
	[
		"naming_series:Select:Series|opt=IMS-.YYYY.-.#####|reqd|default=IMS-.YYYY.-.#####|phide",
		"company:Link:Company|opt=Company|reqd|filter",
		"supplier:Link:Supplier|opt=Supplier|reqd|list|filter",
		"supplier_name:Data:Supplier Name|fetch=supplier.supplier_name|ro",
		"column_break_head:Column Break",
		"status:Select:Status|opt="
		+ STATUSES
		+ "|default=Planned|list|filter|bold|desc=Moves by itself up to Customs Cleared: booking, departure or B/L, arrival, then Bills of Entry.",
		"origin_country:Link:Country of Origin|opt=Country|list|filter",
		"readiness_percent:Percent:Document Readiness|ro|list|nocopy",
		"terms_section:Section Break:Route and Terms",
		"mode_of_transport:Select:Mode|opt=" + MODES + "|default=Sea FCL",
		"port_of_loading:Link:Port of Loading|opt=Port Master|link_filters=" + FOREIGN_PORTS,
		"port_of_discharge:Link:Port of Discharge|opt=Port Master|link_filters=" + INDIAN_PORTS,
		"column_break_terms:Column Break",
		"incoterm:Link:Incoterm|opt=Incoterm",
		"currency:Link:Currency|opt=Currency",
		"orders_section:Section Break:Orders and Invoices",
		"orders:Table:Purchase Orders|opt=Import Shipment Order",
		"invoices:Table:Purchase Invoices|opt=Import Shipment Invoice",
		"notes_section:Section Break:Remarks|collapsible",
		"remarks:Text Editor:Remarks",
		"booking_tab:Tab Break:Booking",
		"carrier_section:Section Break:Carrier and Booking",
		"freight_forwarder:Link:Freight Forwarder|opt=Supplier",
		"cha:Link:Customs Broker (CHA)|opt=Supplier",
		"shipping_line:Data:Shipping Line / Airline",
		"column_break_carrier:Column Break",
		"booking_number:Data:Booking No.",
		"vessel_voyage:Data:Vessel / Voyage or Flight",
		"etd:Date:ETD",
		"eta:Date:ETA|list",
		"containers_section:Section Break:Containers",
		"containers:Table:Containers / Packages|opt=Shipment Container",
		"total_gross_weight:Float:Total Gross Weight (kg)|ro",
		"total_packages:Int:Total Packages|ro",
		"arrival_tab:Tab Break:B/L and Arrival",
		"transport_document_section:Section Break:Bill of Lading / Airway Bill",
		"bl_number:Data:BL / AWB No.",
		"bl_date:Date:BL / AWB Date",
		"column_break_bl:Column Break",
		"bl_type:Select:BL Type|opt=\\nOriginal BL\\nTelex Release\\nSeaway Bill\\nAir Waybill\\nCourier Waybill",
		"atd:Date:Actual Departure",
		"arrival_section:Section Break:Arrival",
		"ata:Date:Actual Arrival",
		"igm_number:Data:IGM No.",
		"igm_date:Date:IGM Date",
		"column_break_arrival:Column Break",
		"free_days:Int:Free Days (Detention / Demurrage)",
		"free_time_ends:Date:Free Time Ends|ro",
		"documents_tab:Tab Break:Documents",
		"documents:Table:Document Checklist|opt=Shipment Document",
		"charges_tab:Tab Break:Charges",
		"charges:Table:Shipment Charges|opt=Shipment Charge",
		"total_charges:Currency:Total Charges|opt=Company:company:default_currency|ro",
		"connections_tab:Tab Break:Connections|dashboard",
	],
	autoname="naming_series:",
	title_field="supplier_name",
	search_fields="supplier,origin_country,booking_number,bl_number",
	roles=ROLES,
	extra={"show_name_in_global_search": 1, "show_title_field_in_link": 0, **STAMP},
)

doctype(
	"Import Shipment Order",
	IMPORTS,
	[
		"purchase_order:Link:Purchase Order|opt=Purchase Order|reqd|list|width=3",
		"transaction_date:Date:Order Date|fetch=purchase_order.transaction_date|ro|list|width=2",
		"currency:Link:Currency|opt=Currency|fetch=purchase_order.currency|ro|list|width=1",
		"grand_total:Currency:Order Value|opt=currency|fetch=purchase_order.grand_total|ro|list|width=2",
	],
	istable=True,
	extra=STAMP,
)

doctype(
	"Import Shipment Invoice",
	IMPORTS,
	[
		"purchase_invoice:Link:Purchase Invoice|opt=Purchase Invoice|reqd|list|width=3",
		"bill_no:Data:Supplier Invoice No.|fetch=purchase_invoice.bill_no|ro|list|width=2",
		"currency:Link:Currency|opt=Currency|fetch=purchase_invoice.currency|ro|list|width=1",
		"grand_total:Currency:Invoice Value|opt=currency|fetch=purchase_invoice.grand_total|ro|list|width=2",
	],
	istable=True,
	extra=STAMP,
)
