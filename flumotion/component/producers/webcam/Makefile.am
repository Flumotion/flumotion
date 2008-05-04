include $(top_srcdir)/common/python.mk

componentdir = $(libdir)/flumotion/python/flumotion/component/producers/webcam

component_DATA = \
	webcam.xml	\
	wizard.glade

component_PYTHON = 	\
	__init__.py	\
	admin_gtk.py	\
	webcam.py	\
	wizard_gtk.py

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
