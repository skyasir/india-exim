const EXIM_ROOT_TYPES = {
	Asset: [
		"exim_drawback_receivable_account",
		"exim_rodtep_receivable_account",
		"exim_rosctl_receivable_account",
		"exim_rodtep_scrip_account",
		"exim_igst_refund_receivable_account",
	],
	Income: [
		"exim_drawback_income_account",
		"exim_rodtep_income_account",
		"exim_rosctl_income_account",
	],
	Expense: [
		"exim_scrip_sale_loss_account",
		"exim_incentive_recovery_account",
		"exim_freight_outward_account",
		"exim_freight_inward_account",
		"exim_clearing_charges_account",
		"exim_export_bank_charges_account",
		"exim_demurrage_account",
		"exim_ecgc_premium_account",
	],
};

frappe.ui.form.on("Company", {
	setup(frm) {
		for (const [root_type, fields] of Object.entries(EXIM_ROOT_TYPES)) {
			for (const fieldname of fields) {
				frm.set_query(fieldname, () => ({
					filters: { company: frm.doc.name, root_type, is_group: 0 },
				}));
			}
		}
		frm.set_query("exim_forex_gain_loss_account", () => ({
			filters: { company: frm.doc.name, is_group: 0 },
		}));
		frm.set_query("exim_cost_center", () => ({
			filters: { company: frm.doc.name, is_group: 0 },
		}));
	},

	refresh(frm) {
		if (frm.is_new() || frm.doc.country !== "India") return;
		frm.add_custom_button(
			__("Create Default EXIM Accounts"),
			() =>
				frappe
					.call({
						method: "india_exim.overrides.company.create_default_exim_accounts",
						args: { company: frm.doc.name },
						freeze: true,
					})
					.then(() => frm.reload_doc()),
			__("Manage")
		);
	},
});
