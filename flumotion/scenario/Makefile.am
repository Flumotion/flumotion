include $(top_srcdir)/common/python.mk

componentdir = $(libdir)/flumotion/python/flumotion/scenario
component_PYTHON = \
	__init__.py

TAGS_FILES = $(component_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

SUBDIRS = \
	live \
	ondemand \
	steps

EXTRA_DIST = $(component_DATA)
