include $(top_srcdir)/common/python.mk

component_PYTHON = __init__.py looper.py admin_gtk.py wizard_gtk.py
componentdir = $(libdir)/flumotion/python/flumotion/component/producers/looper
component_DATA = looper.xml flufileinfo.glade looper.glade wizard.glade 

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
