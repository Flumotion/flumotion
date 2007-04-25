include $(top_srcdir)/common/python.mk

component_PYTHON = __init__.py rtsp.py
componentdir = $(libdir)/flumotion/python/flumotion/component/producers/rtsp
component_DATA = \
	rtsp.xml

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
