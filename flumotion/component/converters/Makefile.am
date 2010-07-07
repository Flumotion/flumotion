include $(top_srcdir)/common/python.mk

consumersdir = $(libdir)/flumotion/python/flumotion/component/converters
consumers_PYTHON = \
	__init__.py

TAGS_FILES = $(component_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

SUBDIRS = 	\
	overlay \
	pipeline\
	video

