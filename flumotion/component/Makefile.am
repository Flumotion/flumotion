componentdir = $(libdir)/flumotion/python/flumotion/component
component_PYTHON = \
	__init__.py \
	feedcomponent.py \
	component.py

TAGS_FILES = $(component_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

SUBDIRS = \
	consumers \
	base \
	bouncers \
	encoders \
	muxers \
	producers \
	overlay \
	webcam
