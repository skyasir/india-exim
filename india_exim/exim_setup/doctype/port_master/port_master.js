// Copyright (c) 2026, Yasir Shaikh and contributors
// For license information, please see license.txt

frappe.ui.form.on("Port Master", {
	refresh(frm) {
		// Frappe hides the field a record is named by once it is saved; the code is what customs
		// and the shipping line use, so it stays in view. It is changed with Rename.
		frm.toggle_display("port_code", true);
		frm.set_df_property("port_code", "read_only", frm.is_new() ? 0 : 1);
	},
});
