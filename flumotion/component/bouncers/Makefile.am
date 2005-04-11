include $(top_srcdir)/common/python.mk
                                                                                
componentdir = $(libdir)/flumotion/python/flumotion/component/bouncers
component_PYTHON = \
	__init__.py \
	admin_gtk.py \
	htpasswdcrypt.py \
	bouncer.py

component_DATA = htpasswdcrypt.xml bouncer.glade


TAGS_FILES = $(component_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
