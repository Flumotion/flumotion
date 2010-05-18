include $(top_srcdir)/common/python.mk

decodersdir = $(libdir)/flumotion/python/flumotion/component/decoders
decoders_PYTHON = \
	__init__.py
decoders_DATA = decoders.xml

TAGS_FILES = $(decoders_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

SUBDIRS = \
	generic

EXTRA_DIST = $(decoders_DATA)
