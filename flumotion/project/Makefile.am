include $(top_srcdir)/common/python.mk
include $(top_srcdir)/common/locale.mk

flumotiondir = $(libdir)/flumotion/python/flumotion/project

flumotion_PYTHON = \
	__init__.py \
	project.py
flumotion_DATA = flumotion.locale.xml

clean-local:
	rm -rf *.pyc *.pyo

PROJECT = flumotion
BUILT_SOURCES = flumotion.locale.xml
CLEANFILES = $(BUILT_SOURCES)
