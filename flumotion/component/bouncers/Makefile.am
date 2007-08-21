include $(top_srcdir)/common/python.mk
                                                                                
componentdir = $(libdir)/flumotion/python/flumotion/component/bouncers
component_PYTHON = \
	__init__.py \
	admin_gtk.py \
	bouncer.py \
	component.py \
	plug.py \
	htpasswdcrypt.py \
	saltsha256.py \
	tokentest.py \
	ipbouncer.py \
	icalbouncer.py

component_DATA = htpasswdcrypt.xml saltsha256.xml bouncer.glade tokentest.xml \
	ipbouncer.py icalbouncer.xml deprecated.xml bouncer.xml


TAGS_FILES = $(component_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
