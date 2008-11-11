include $(top_srcdir)/common/python.mk

componentdir = $(libdir)/flumotion/python/flumotion/scenario/ondemand
component_PYTHON = \
		__init__.py \
		wizard_gtk.py

TAGS_FILES = $(component_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
