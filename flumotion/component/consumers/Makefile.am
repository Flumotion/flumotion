include $(top_srcdir)/python.mk
                                                                                
consumersdir = $(libdir)/flumotion/python/flumotion/component/consumers
consumers_PYTHON = \
	__init__.py

TAGS_FILES = $(component_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

SUBDIRS = \
	disker \
	httpstreamer
