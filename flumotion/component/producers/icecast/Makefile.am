include $(top_srcdir)/common/python.mk

component_PYTHON = __init__.py icecast.py
componentdir = $(libdir)/flumotion/python/flumotion/component/producers/icecast
component_DATA = icecast.xml

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
