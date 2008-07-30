CONFIG = 						\
	examples/bouncer.xml				\
	examples/ipbouncer.xml				\
	examples/twores.xml				\
	examples/default.xml 				\
	examples/discont.xml 				\
	examples/ondemand.xml

EXTRA_DIST = 						\
        default.pem					\
	managers/default/adminactionfilelogger.xml	\
	managers/default/exampleidentityprovider.xml	\
	managers/default/managerlifecycleprinter.xml	\
	managers/default/manhole.xml			\
	managers/default/planet.xml			\
	managers/default/flows/ogg-test-theora.xml	\
	workers/default.xml 				\
	$(CONFIG)

check:
	for f in $(CONFIG); do $(top_builddir)/env python $(top_srcdir)/misc/validate-config.py $(srcdir)/$$f; done
