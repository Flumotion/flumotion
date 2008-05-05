include $(top_srcdir)/common/python.mk

component_PYTHON = 		\
	__init__.py		\
	audiotest.py		\
	admin_gtk.py		\
	wizard_gtk.py

componentdir = $(libdir)/flumotion/python/flumotion/component/producers/audiotest
component_DATA = 		\
	audiotest.xml		\
	audiotest.glade		\
	wizard.glade

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
