include $(top_srcdir)/common/python.mk

componentdir = $(libdir)/flumotion/python/flumotion/admin
component_PYTHON = \
	__init__.py \
	admin.py \
	config.py \
	connections.py \
	multi.py

SUBDIRS = assistant command gtk rrdmon text

TAGS_FILES = $(component_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo
