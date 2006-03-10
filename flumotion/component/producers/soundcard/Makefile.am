include $(top_srcdir)/common/python.mk

component_PYTHON = __init__.py soundcard.py admin_gtk.py checks.py
componentdir = $(libdir)/flumotion/python/flumotion/component/producers/soundcard
component_DATA = soundcard.xml

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
