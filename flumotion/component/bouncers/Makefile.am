include $(top_srcdir)/common/python.mk

componentdir = $(libdir)/flumotion/python/flumotion/component/bouncers
component_PYTHON = \
	__init__.py \
	admin_gtk.py \
	bouncer.py \
	component.py \
	htpasswdcrypt.py \
	icalbouncer.py \
	ipbouncer.py \
	saltsha256.py \
	plug.py \
	tokentest.py \
	tokentestbouncer.py

component_DATA = htpasswdcrypt.xml saltsha256.xml bouncer.glade tokentest.xml \
	icalbouncer.xml deprecated.xml bouncer.xml


TAGS_FILES = $(component_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
