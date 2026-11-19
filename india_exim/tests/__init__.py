def before_tests():
	"""Reuse India Compliance's test company, parties and GST setup."""
	from india_compliance.tests import before_tests as india_compliance_before_tests

	india_compliance_before_tests()
