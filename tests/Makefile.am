tests =  \
	manager.py

check-local:
	@PYTHONPATH=$(top_builddir):$(PYTHONPATH) $(PYTHON) $(srcdir)/runtests.py
	@rm -fr *.pyc

EXTRA_DIST = $(tests) runtests.py
