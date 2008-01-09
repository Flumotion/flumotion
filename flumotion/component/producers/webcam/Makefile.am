include $(top_srcdir)/common/python.mk

componentdir = $(libdir)/flumotion/python/flumotion/component/producers/webcam

component_DATA = \
	webcam.xml	\
	webcam-wizard.glade

component_PYTHON = 	\
	__init__.py	\
	admin_gtk.py	\
	webcam.py	\
	webcam_wizard.py

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
