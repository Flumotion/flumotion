include $(top_srcdir)/common/python.mk
                                                                                
componentdir = $(libdir)/flumotion/python/flumotion/admin
component_PYTHON = \
	__init__.py \
	admin.py \
	connections.py

SUBDIRS = gtk

TAGS_FILES = $(component_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo
