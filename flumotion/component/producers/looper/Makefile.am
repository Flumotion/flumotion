include $(top_srcdir)/common/python.mk

component_PYTHON = __init__.py looper.py #admin_gtk.py
componentdir = $(libdir)/flumotion/python/flumotion/component/producers/looper
component_DATA = looper.xml

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
