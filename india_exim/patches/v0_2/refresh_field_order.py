"""The Export & Import fields were rearranged; sites with a saved field order need it refreshed."""

from india_exim.install import setup_custom_fields
from india_exim.setup.field_order import refresh_field_order


def execute():
	setup_custom_fields()
	refresh_field_order()
