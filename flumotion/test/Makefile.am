EXTRA_DIST = \
	test_bundle.py \
	test_common.py \
	test_component.py \
	test_config.py \
	test_enum.py \
	test_configure.py \
	test_http.py \
	test_log.py \
	test_manager.py \
	test_registry.py

check-local:
	@if PYTHONPATH=$(top_srcdir):$(PYTHONPATH) trial -R flumotion.test; \
	then \
	    rm -fr $(top_builddir)/flumotion/test/_trial_temp; \
	else \
	    exit 1; \
	fi
	@rm -fr $(top_builddir)/flumotion/test/*.pyc
