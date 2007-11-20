include $(top_srcdir)/common/python.mk

component_PYTHON = __init__.py composite.py
componentdir = $(libdir)/flumotion/python/flumotion/component/combiners/composite
component_DATA = \
	composite.xml

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
