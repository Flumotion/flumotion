include $(top_srcdir)/common/python.mk

component_PYTHON = 		\
	__init__.py		\
	generic.py

componentdir = $(libdir)/flumotion/python/flumotion/component/decoders/generic
component_DATA = 		\
	generic.xml

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
