check-local:
	@PYTHONPATH=$(top_builddir):$(PYTHONPATH) $(PYTHON) $(srcdir)/runtests.py
	@rm -fr *.pyc

SUBDIRS = tests

EXTRA_DIST = runtests.py
