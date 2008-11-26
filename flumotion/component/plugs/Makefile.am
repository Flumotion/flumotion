include $(top_srcdir)/common/python.mk

SUBDIRS = cortado

component_PYTHON = \
	__init__.py \
	adminaction.py \
	base.py \
	identity.py \
	manhole.py \
	request.py \
	rrd.py \
	streamdata.py \
	requestmodifier.py

componentdir = $(libdir)/flumotion/python/flumotion/component/plugs
component_DATA = plugs.xml

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
