include $(top_srcdir)/common/python.mk
                                                                                
componentdir = $(libdir)/flumotion/python/flumotion/component
component_DATA = component.xml
component_PYTHON = \
	__init__.py \
	feedcomponent.py \
	component.py

TAGS_FILES = $(component_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

SUBDIRS = \
	base \
	bouncers \
	consumers \
	converters \
	effects \
	encoders \
	muxers \
	producers

EXTRA_DIST = $(component_DATA)
