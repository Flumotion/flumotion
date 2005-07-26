include $(top_srcdir)/common/python.mk
                                                                                
EXTRA_DIST = 				\
	test.xml			\
	__init__.py			\
	common.py			\
	gtkunit.py			\
	test_bundle.py 			\
	test_checkers.py 		\
	test_common.py 			\
	test_common_componentui.py 	\
	test_common_gstreamer.py 	\
	test_common_package.py	 	\
	test_common_planet.py	 	\
	test_common_pygobject.py 	\
	test_component.py 		\
	test_config.py 			\
	test_credentials.py 		\
	test_dag.py	 		\
	test_defer.py			\
	test_dialogs.py 		\
	test_enum.py 			\
	test_flavors.py 		\
	test_greeter.py			\
	test_htpasswdcrypt.py 		\
	test_http.py 			\
	test_keycards.py 		\
	test_log.py 			\
	test_manager_admin.py 		\
	test_manager_manager.py 	\
	test_manager_worker.py		\
	test_parts.py	 		\
	test_pb.py	 		\
	test_pygobject.py		\
	test_reflect.py 		\
	test_registry.py 		\
	test_twisted_compat.py 		\
	test_ui_fgtk.py 		\
	test_wizard.py 			\
	test_workerconfig.py

check-local: rm-test-log
	@if PYTHONPATH=$(top_srcdir):$(PYTHONPATH)			\
	trial -l test.log -R flumotion.test;				\
	then 								\
	    rm -fr $(top_builddir)/flumotion/test/_trial_temp;		\
	    if test -e test.log; then					\
		if grep "Could not import" test.log > /dev/null; then	\
	            exit 1;						\
		fi;							\
	    fi;								\
            make rm-test-log;						\
	else								\
            make rm-test-log;						\
	    exit 1;							\
	fi
	@rm -fr $(top_builddir)/flumotion/test/*.pyc

rm-test-log:
	@if test -e test.log; then rm test.log; fi
