include $(top_srcdir)/common/python.mk

component_PYTHON = __init__.py bttv.py admin_gtk.py
componentdir = $(libdir)/flumotion/python/flumotion/component/producers/bttv
component_DATA = bttv.xml colorbalance.glade

clean-local:
	rm -rf *.pyc *.pyo

# PYCHECKER_FILES = $(component_PYTHON)

EXTRA_DIST = $(component_DATA)
