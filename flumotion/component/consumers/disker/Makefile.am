include $(top_srcdir)/python.mk

componentdir = $(libdir)/flumotion/python/flumotion/component/consumers/disker

component_PYTHON = \
	__init__.py \
	disker.py  \
	admin_gtk.py

component_DATA = disker.xml disker.glade

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
