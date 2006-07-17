include $(top_srcdir)/common/python.mk

gdptestsrcdir = $(libdir)/flumotion/python/flumotion/component/misc/gdptestsrc

gdptestsrc_PYTHON = \
	__init__.py 	\
	gdptestsrc.py

gdptestsrc_DATA = gdptestsrc.xml

TAGS_FILES = $(gdptestsrc_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(gdptestsrc_PYTHON) $(gdptestsrc_DATA)
