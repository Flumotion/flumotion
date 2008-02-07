include $(top_srcdir)/common/python.mk

component_PYTHON = \
	__init__.py \
	http.py \
	resources.py \
	admin_gtk.py \
	http_wizard.py

componentdir = $(libdir)/flumotion/python/flumotion/component/consumers/httpstreamer
component_DATA = http.xml http.glade http-wizard.glade

clean-local:
	rm -rf *.pyc *.pyo

# PYCHECKER_FILES = $(component_PYTHON)

EXTRA_DIST = $(component_PYTHON) $(component_DATA)
