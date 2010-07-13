include $(top_srcdir)/common/python.mk

component_PYTHON = __init__.py genimg.py overlay.py
componentdir = $(libdir)/flumotion/python/flumotion/component/converters/overlay
component_DATA = \
	overlay.xml

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
