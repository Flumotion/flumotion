include $(top_srcdir)/common/python.mk

component_PYTHON = __init__.py audioresync.py admin_gtk.py
componentdir = $(libdir)/flumotion/python/flumotion/component/effects/audioresync
component_DATA = audioresync.xml audioresync.glade

clean-local:
	rm -rf *.pyc *.pyo

# PYCHECKER_FILES = $(component_PYTHON)

EXTRA_DIST = $(component_DATA)
