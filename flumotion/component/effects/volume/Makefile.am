include $(top_srcdir)/python.mk

component_PYTHON = __init__.py volume.py admin_gtk.py
componentdir = $(libdir)/flumotion/python/flumotion/component/effects/volume
component_DATA = volume.xml volume.glade

clean-local:
	rm -rf *.pyc *.pyo

# PYCHECKER_FILES = $(component_PYTHON)

EXTRA_DIST = $(component_DATA)
