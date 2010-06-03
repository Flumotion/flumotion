include $(top_srcdir)/common/python.mk

componentdir = $(libdir)/flumotion/python/flumotion/component/bouncers
component_PYTHON = \
	__init__.py \
	base.py \
	admin_gtk.py \
	component.py \
	htpasswdcrypt.py \
	icalbouncer.py \
	ipbouncer.py \
	saltsha256.py \
	plug.py \
	tokentestbouncer.py \
	multibouncer.py \
	multibouncerplug.py \
	combinator.py

component_DATA = base.xml component.xml plug.xml htpasswdcrypt.xml \
	saltsha256.xml bouncer.glade tokentest.xml ipbouncer.xml \
	icalbouncer.xml multibouncer.xml multibouncerplug.xml


TAGS_FILES = $(component_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

SUBDIRS = algorithms

EXTRA_DIST = $(component_DATA)
