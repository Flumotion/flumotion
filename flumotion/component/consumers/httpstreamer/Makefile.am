include $(top_srcdir)/python.mk

component_PYTHON = \
	__init__.py \
	http.py \
	resources.py \
	admin_gtk.py

componentdir = $(libdir)/flumotion/python/flumotion/component/consumers/httpstreamer
component_DATA = http.xml http.glade

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_PYTHON) $(component_DATA)
