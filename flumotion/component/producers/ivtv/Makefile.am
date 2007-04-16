include $(top_srcdir)/common/python.mk

component_PYTHON = __init__.py ivtv.py
componentdir = $(libdir)/flumotion/python/flumotion/component/producers/ivtv
component_DATA = \
	ivtv.xml

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
