include $(top_srcdir)/common/python.mk

componentdir = $(libdir)/flumotion/python/flumotion/component/producers/firewire
component_DATA = 		\
	firewire.xml		\
	firewire-wizard.glade

component_PYTHON = 		\
	__init__.py 		\
	admin_gtk.py		\
	firewire.py		\
	firewire_wizard.py

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
