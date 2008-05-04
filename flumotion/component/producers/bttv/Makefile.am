include $(top_srcdir)/common/python.mk

componentdir = $(libdir)/flumotion/python/flumotion/component/producers/bttv
component_DATA = 		\
	bttv.xml		\
	wizard.glade	\
	colorbalance.glade

component_PYTHON = 		\
	__init__.py		\
	admin_gtk.py		\
	bttv.py			\
	wizard_gtk.py

clean-local:
	rm -rf *.pyc *.pyo

# PYCHECKER_FILES = $(component_PYTHON)

EXTRA_DIST = $(component_DATA)
