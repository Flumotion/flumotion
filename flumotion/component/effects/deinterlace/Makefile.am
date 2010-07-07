include $(top_srcdir)/common/python.mk

component_PYTHON = __init__.py deinterlace.py admin_gtk.py
componentdir = $(libdir)/flumotion/python/flumotion/component/effects/deinterlace
component_DATA = deinterlace.xml deinterlace.glade

clean-local:
	rm -rf *.pyc *.pyo

# PYCHECKER_FILES = $(component_PYTHON)

EXTRA_DIST = $(component_DATA)
