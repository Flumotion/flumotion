# all tests ran by runtests.py live in the tests srcdir, so add it
# to PYTHONPATH so they can be imported
check-local:
	@PYTHONPATH=$(top_builddir):$(top_srcdir)/testsuite/tests:$(PYTHONPATH) $(PYTHON) $(srcdir)/runtests.py
	@rm -fr *.pyc

SUBDIRS = tests

EXTRA_DIST = runtests.py
