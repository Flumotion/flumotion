include $(top_srcdir)/common/python.mk

repeaterdir = $(libdir)/flumotion/python/flumotion/component/misc/repeater

repeater_PYTHON = \
	__init__.py 	\
	repeater.py

repeater_DATA = repeater.xml

TAGS_FILES = $(repeater_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(repeater_PYTHON) $(repeater_DATA)
