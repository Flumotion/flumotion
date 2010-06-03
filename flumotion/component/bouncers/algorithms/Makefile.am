	include $(top_srcdir)/common/python.mk

componentdir = $(libdir)/flumotion/python/flumotion/component/bouncers/algorithms
component_PYTHON = \
	__init__.py \
	base.py \
	icalbouncer.py \
	ipbouncer.py \
	tokentest.py

component_DATA = base.xml ipbouncer.xml icalbouncer.xml tokentest.xml

TAGS_FILES = $(component_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
