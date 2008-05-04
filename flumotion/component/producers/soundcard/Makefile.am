include $(top_srcdir)/common/python.mk

componentdir = $(libdir)/flumotion/python/flumotion/component/producers/soundcard

component_DATA = 		\
	soundcard.xml		\
	wizard.glade

component_PYTHON = 		\
	__init__.py		\
	admin_gtk.py		\
	soundcard.py		\
	wizard_gtk.py


clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
