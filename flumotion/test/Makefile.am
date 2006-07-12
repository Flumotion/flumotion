include $(top_srcdir)/common/python.mk
include $(top_srcdir)/common/trial.mk
                                                                                
flumotiondir = $(libdir)/flumotion/python/flumotion/test

flumotion_PYTHON =			\
        __init__.py			\
	common.py			\
	testclasses.py			\
	gtkunit.py

EXTRA_DIST = 				\
	test.xml			\
	test_admin_multi.py		\
	test_bundle.py 			\
	test_checkers.py 		\
	test_common.py 			\
	test_common_componentui.py 	\
	test_common_connection.py 	\
	test_common_gstreamer.py 	\
	test_common_messages.py 	\
	test_common_package.py	 	\
	test_common_planet.py	 	\
	test_common_pygobject.py 	\
	test_component.py 		\
	test_component_init.py 		\
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
	test_i18n.py 			\
	test_keycards.py 		\
	test_log.py 			\
	test_manager_admin.py 		\
	test_manager_manager.py 	\
	test_manager_worker.py		\
	test_parts.py	 		\
	test_pb.py	 		\
	test_pbstream.py		\
	test_porter.py	 		\
	test_reflect.py 		\
	test_registry.py 		\
	test_testclasses.py 		\
	test_twisted_compat.py 		\
	test_ui_fgtk.py 		\
	test_wizard.py 			\
	test_workerconfig.py

check-local: trial
