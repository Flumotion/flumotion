include $(top_srcdir)/common/common.mk

CONFIG = 						\
	examples/bouncer.xml				\
	examples/ipbouncer.xml				\
	examples/twores.xml				\
	examples/default.xml 				\
	examples/discont.xml 				\
	examples/ondemand.xml 				\
	examples/ondemand-cache.xml

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

check-local: check-local-config
