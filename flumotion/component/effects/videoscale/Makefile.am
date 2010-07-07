include $(top_srcdir)/common/python.mk

component_PYTHON = __init__.py videoscale.py admin_gtk.py
componentdir = $(libdir)/flumotion/python/flumotion/component/effects/videoscale
component_DATA = videoscale.xml videoscale.glade

clean-local:
	rm -rf *.pyc *.pyo

# PYCHECKER_FILES = $(component_PYTHON)

EXTRA_DIST = $(component_DATA)
