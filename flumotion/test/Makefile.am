EXTRA_DIST = 			\
	test_bundle.py 		\
	test_checkers.py 	\
	test_common.py 		\
	test_component.py 	\
	test_config.py 		\
	test_credentials.py 	\
	test_enum.py 		\
	test_htpasswdcrypt.py 	\
	test_http.py 		\
	test_keycards.py 	\
	test_log.py 		\
	test_manager.py 	\
	test_manager_admin.py 	\
	test_reflect.py 	\
	test_registry.py 	\
	test_wizard.py 		\
	test_workerconfig.py 	\
	test_worker_heaven.py

check-local:
	@if PYTHONPATH=$(top_srcdir):$(PYTHONPATH) trial -R flumotion.test; \
	then \
	    rm -fr $(top_builddir)/flumotion/test/_trial_temp; \
	else \
	    exit 1; \
	fi
	@rm -fr $(top_builddir)/flumotion/test/*.pyc
