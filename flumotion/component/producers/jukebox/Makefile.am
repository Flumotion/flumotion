include $(top_srcdir)/common/python.mk

component_PYTHON = \
	__init__.py \
	jukebox09.py

componentdir = $(libdir)/flumotion/python/flumotion/component/producers/jukebox
component_DATA = jukebox.xml

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
