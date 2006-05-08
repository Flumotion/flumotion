include $(top_srcdir)/common/python.mk
                                                                                
componentdir = $(libdir)/flumotion/python/flumotion/component
component_DATA = component.xml
component_PYTHON = \
	__init__.py \
	component.py \
	feedcomponent.py \
	feedcomponent08.py \
	feedcomponent010.py

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
	plugs \
	porter \
	producers

EXTRA_DIST = $(component_DATA)
