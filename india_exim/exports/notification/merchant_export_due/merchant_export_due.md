Goods bought from **{{ doc.supplier_name }}** at the concessional 0.1% GST (invoice {{ doc.bill_no or doc.name }} dated {{ frappe.format_value(doc.bill_date or doc.posting_date, {"fieldtype": "Date"}) }}) must be exported by **{{ frappe.format_value(doc.exim_merchant_export_due, {"fieldtype": "Date"}) }}**.

No shipping bill is linked to this purchase yet. If the goods are not exported in time, the supplier will have to charge GST at the full rate.

Once shipped, set **Exported Under Shipping Bill** on the purchase invoice and send the shipping bill and EGM copy to the supplier.
