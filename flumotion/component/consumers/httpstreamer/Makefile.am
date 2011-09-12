include $(top_srcdir)/common/python.mk

component_PYTHON = 		\
	__init__.py 		\
	httpstreamer.py 	\
	icystreamer.py  	\
	icymux.py 		\
	resources.py 		\
	admin_gtk.py 		\
	wizard_gtk.py

componentdir = $(libdir)/flumotion/python/flumotion/component/consumers/httpstreamer
component_DATA = 			\
	httpstreamer.xml 		\
	icytab.glade			\
	wizard.glade

clean-local:
	rm -rf *.pyc *.pyo

# PYCHECKER_FILES = $(component_PYTHON)

EXTRA_DIST = $(component_PYTHON) $(component_DATA)
