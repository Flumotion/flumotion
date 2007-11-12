include $(top_srcdir)/common/python.mk
include $(top_srcdir)/common/trial.mk
TRIAL_ENV=$(top_builddir)/env

flumotiondir = $(libdir)/flumotion/python/flumotion/test

flumotion_PYTHON =			\
        __init__.py			\
	testclasses.py			\
	comptest.py			\
	gtkunit.py			\
	realm.py

EXTRA_DIST = 				\
	bouncertest.py			\
	test.xml			\
	testLoadComponent.xml		\
	test_admin_admin.py		\
	test_admin_multi.py		\
	test_bundle.py 			\
	test_checkers.py 		\
	test_common.py 			\
	test_common_avltree.py	 	\
	test_common_componentui.py 	\
	test_common_connection.py 	\
	test_common_gstreamer.py 	\
	test_common_messages.py 	\
	test_common_netutils.py 	\
	test_common_package.py	 	\
	test_common_planet.py	 	\
	test_common_pygobject.py 	\
	test_common_signals.py	 	\
	test_component.py 		\
	test_component_base_scheduler.py\
	test_component_base_watcher.py  \
	test_component_bouncers_bouncer.py\
	test_component_bouncers_component.py\
	test_component_bouncers_plug.py\
	test_component_init.py 		\
	test_component_feed.py		\
	test_component_feeder.py	\
	test_component_httpserver.py 	\
	test_component_httpstreamer.py 	\
	test_component_padmonitor.py 	\
	test_component_playlist.py 	\
	test_comptest.py 		\
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
	test_manager_admin.py 		\
	test_manager_manager.py 	\
	test_manager_worker.py		\
	test_misc_httpfile.py		\
	test_parts.py	 		\
	test_pb.py	 		\
	test_pbstream.py		\
	test_porter.py	 		\
	test_reflect.py 		\
	test_registry.py 		\
	test_testclasses.py 		\
	test_twisted_integration.py 	\
	test_ui_fgtk.py 		\
	test_wizard.py 			\
	test_workerconfig.py		\
	test_worker_config.py		\
	test_worker_medium.py		\
	test_worker_worker.py

check-local: trial
