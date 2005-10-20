include $(top_srcdir)/common/python.mk

componentdir = $(libdir)/flumotion/python/flumotion/component/consumers/preview

component_PYTHON = \
	__init__.py \
	preview.py

component_DATA = preview.xml

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
