// Consignee, Buyer and Notify Party on the Export Details tab: pick a Customer,
// then one of its Addresses and Contacts; the text under each link fills in.
// See india_exim/utils/parties.py.
(() => {
	// loaded for several doctypes, so evaluated once per form type; register once
	if (window.__exim_parties_loaded) return;
	window.__exim_parties_loaded = true;

	const PARTIES = ["consignee", "buyer", "notify"];
	const METHOD = "india_exim.utils.parties.get_party_details";

	const fetch_details = (frm, party, args) =>
		frappe.call({ method: METHOD, args }).then(({ message: details = {} }) => {
			const values = {};
			if ("address" in details) values[`exim_${party}_address`] = details.address;
			if ("contact" in details) values[`exim_${party}_contact`] = details.contact;
			if ("address_display" in details) values[`exim_${party}_address_display`] = details.address_display;
			if ("contact_display" in details) values[`exim_${party}_contact_display`] = details.contact_display;
			// the links set here must not fetch again through their own handlers
			frm.__exim_filling = true;
			return Promise.resolve(frm.set_value(values)).finally(() => (frm.__exim_filling = false));
		});

	const handlers = {
		setup(frm) {
			for (const party of PARTIES) {
				const filters = () => {
					const customer = frm.doc[`exim_${party}`];
					return customer ? { link_doctype: "Customer", link_name: customer } : {};
				};
				frm.set_query(`exim_${party}_address`, () => ({
					query: "frappe.contacts.doctype.address.address.address_query",
					filters: filters(),
				}));
				frm.set_query(`exim_${party}_contact`, () => ({
					query: "frappe.contacts.doctype.contact.contact.contact_query",
					filters: filters(),
				}));
			}
		},
	};

	for (const party of PARTIES) {
		handlers[`exim_${party}`] = (frm) => {
			if (frm.__exim_filling) return;
			const customer = frm.doc[`exim_${party}`];
			if (!customer) {
				return frm.set_value({
					[`exim_${party}_address`]: "",
					[`exim_${party}_address_display`]: "",
					[`exim_${party}_contact`]: "",
					[`exim_${party}_contact_display`]: "",
				});
			}
			return fetch_details(frm, party, { customer });
		};

		handlers[`exim_${party}_address`] = (frm) => {
			if (frm.__exim_filling) return;
			const address = frm.doc[`exim_${party}_address`];
			if (!address) return frm.set_value(`exim_${party}_address_display`, "");
			return fetch_details(frm, party, { address });
		};

		handlers[`exim_${party}_contact`] = (frm) => {
			if (frm.__exim_filling) return;
			const contact = frm.doc[`exim_${party}_contact`];
			if (!contact) return frm.set_value(`exim_${party}_contact_display`, "");
			return fetch_details(frm, party, { contact });
		};
	}

	frappe.ui.form.on("Quotation", handlers);
	frappe.ui.form.on("Sales Order", handlers);
	frappe.ui.form.on("Delivery Note", handlers);
	frappe.ui.form.on("Sales Invoice", handlers);
})();
