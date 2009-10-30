include $(top_srcdir)/common/python.mk
include $(top_srcdir)/common/trial.mk
TRIAL_ENV=$(top_builddir)/env

flumotiondir = $(libdir)/flumotion/python/flumotion/test

flumotion_PYTHON =			\
        __init__.py			\
	common.py			\
	comptest.py			\
	gtkunit.py			\
	realm.py

EXTRA_DIST = 					\
	testLoadComponent.xml			\
	test.xml				\
	bouncertest.py				\
	test_admin_admin.py			\
	test_admin_config.py			\
	test_admin_connections.py		\
	test_admin_multi.py			\
	test_checkers.py			\
	test_common.py				\
	test_common_avltree.py			\
	test_common_bundle.py			\
	test_common_componentui.py		\
	test_common_connection.py		\
	test_common_eventcalendar.py		\
	test_common_format.py			\
	test_common_gstreamer.py		\
	test_common_messages.py			\
	test_common_netutils.py			\
	test_common_package.py			\
	test_common_planet.py			\
	test_common_process.py			\
	test_common_pygobject.py		\
	test_common_signals.py			\
	test_common_vfs.py			\
	test_common_xdg.py			\
	test_common_xmlwriter.py		\
	test_component_base_scheduler.py	\
	test_component_base_watcher.py		\
	test_component_bouncers_bouncer.py	\
	test_component_bouncers_bouncer_authsession.py	\
	test_component_bouncers_component.py	\
	test_component_bouncers_plug.py		\
	test_component_feeder.py		\
	test_component_feed.py			\
	test_component_feedcomponent.py     \
	test_component_httpserver.py		\
	test_component_httpstreamer.py		\
	test_component_init.py			\
	test_component_padmonitor.py		\
	test_component_playlist.py		\
	test_component.py			\
	test_comptest.py			\
	test_config.py				\
	test_configure.py			\
	test_credentials.py			\
	test_dag.py				\
	test_defer.py				\
	test_dialogs.py				\
	test_enum.py				\
	test_flavors.py				\
	test_greeter.py				\
	test_htpasswdcrypt.py			\
	test_http.py				\
	test_i18n.py				\
	test_import.py				\
	test_keycards.py			\
	test_launch_parse.py			\
	test_logfilter.py			\
	test_manager_admin.py			\
	test_manager_config.py			\
	test_manager_manager.py			\
	test_manager_worker.py			\
	test_options.py				\
	test_parts.py				\
	test_pb.py				\
	test_pbstream.py			\
	test_porter.py				\
	test_public_ui_api.py			\
	test_reflect.py				\
	test_registry.py			\
	test_saltsha256.py			\
	test_testclasses.py			\
	test_twisted_integration.py		\
	test_ui_fgtk.py				\
	test_wizard_models.py			\
	test_wizard.py				\
	test_wizard_save.py			\
	test_worker_config.py			\
	test_workerconfig.py			\
	test_worker_job.py			\
	test_worker_medium.py			\
	test_worker_worker.py			\
	urgent.ics				\
	test-exdate.ics				\
	test-google.ics

check-local: trial
