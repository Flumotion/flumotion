include $(top_srcdir)/common/python.mk

multibitratedir = $(libdir)/flumotion/python/flumotion/component/plugs/hlsmultibitrate

multibitrate_PYTHON = \
	__init__.py	\
	multibitrate.py

multibitrate_DATA = multibitrate.xml

TAGS_FILES = $(multibitrate_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(multibitrate_PYTHON) $(multibitrate_DATA)
