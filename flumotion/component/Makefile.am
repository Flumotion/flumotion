include $(top_srcdir)/common/python.mk

componentdir = $(libdir)/flumotion/python/flumotion/component
component_DATA = component.xml
component_PYTHON = \
	__init__.py \
	component.py \
	decodercomponent.py \
	eater.py \
	feed.py \
	feeder.py \
	feedcomponent.py \
	feedcomponent010.py \
	padmonitor.py

TAGS_FILES = $(component_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

SUBDIRS = \
	base \
	bouncers \
	combiners \
	consumers \
	converters \
	decoders \
	effects \
	encoders \
	misc \
	muxers \
	plugs \
	producers

EXTRA_DIST = $(component_DATA)
