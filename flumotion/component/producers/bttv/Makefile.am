include $(top_srcdir)/common/python.mk

componentdir = $(libdir)/flumotion/python/flumotion/component/producers/bttv
component_DATA = 		\
	bttv.xml		\
	bttv-wizard.glade	\
	colorbalance.glade

component_PYTHON = 		\
	__init__.py		\
	admin_gtk.py		\
	bttv.py			\
	bttv_wizard.py

clean-local:
	rm -rf *.pyc *.pyo

# PYCHECKER_FILES = $(component_PYTHON)

EXTRA_DIST = $(component_DATA)
