include $(top_srcdir)/common/python.mk

SUBDIRS = cortado hlsmultibitrate html5 utils

component_PYTHON = \
	__init__.py \
	adminaction.py \
	base.py \
	identity.py \
	manhole.py \
	request.py \
	requestmodifier.py \
	rrd.py \
	streamdata.py \
  streamerdata.py \
        wizard.glade \
        wizard_gtk.py

componentdir = $(libdir)/flumotion/python/flumotion/component/plugs
component_DATA = plugs.xml

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
