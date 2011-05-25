include $(top_srcdir)/common/python.mk

componentdir = $(libdir)/flumotion/python/flumotion/component/producers/blackmagic
component_DATA = 		\
	blackmagic.xml

component_PYTHON = 		\
	__init__.py 		\
	admin_gtk.py		\
	blackmagic.py

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
