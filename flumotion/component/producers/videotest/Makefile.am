include $(top_srcdir)/common/python.mk

component_PYTHON = 		\
	__init__.py		\
	admin_gtk.py		\
	admin_text.py		\
	videotest.py		\
	wizard_gtk.py

componentdir = $(libdir)/flumotion/python/flumotion/component/producers/videotest
component_DATA = \
	videotest.xml		\
	wizard.glade

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
