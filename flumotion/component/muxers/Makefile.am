include $(top_srcdir)/common/python.mk

component_PYTHON = \
	__init__.py \
	base.py \
	checks.py \
	multipart.py \
	ogg.py \
	wizard_gtk.py

componentdir = $(libdir)/flumotion/python/flumotion/component/muxers
component_DATA = muxers.xml

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
