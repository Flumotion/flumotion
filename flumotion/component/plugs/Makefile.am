include $(top_srcdir)/common/python.mk

component_PYTHON = __init__.py loggers.py
componentdir = $(libdir)/flumotion/python/flumotion/component/plugs
component_DATA = plugs.xml

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
