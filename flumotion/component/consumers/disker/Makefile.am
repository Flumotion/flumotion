include $(top_srcdir)/common/python.mk

componentdir = $(libdir)/flumotion/python/flumotion/component/consumers/disker

component_PYTHON = \
	__init__.py \
	disker.py  \
	disker_plug.py  \
	admin_gtk.py \
	admin_text.py

component_DATA = disker.xml disker.glade status.glade

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
