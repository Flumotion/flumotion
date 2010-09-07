include $(top_srcdir)/common/python.mk

componentdir = $(libdir)/flumotion/python/flumotion/component/effects
component_PYTHON = \
	__init__.py

TAGS_FILES = $(component_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

SUBDIRS = \
	audiorate \
	colorbalance \
	deinterlace  \
	videorate \
	videoscale \
	volume
