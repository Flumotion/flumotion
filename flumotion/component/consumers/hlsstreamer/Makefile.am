include $(top_srcdir)/common/python.mk

component_PYTHON = __init__.py \
		   common.py \
		   resources.py \
		   hlsstreamer.py \
		   hlsring.py \
		   hlssink.py \
		   admin_gtk.py

componentdir = $(libdir)/flumotion/python/flumotion/component/consumers/hlsstreamer
component_DATA = \
	hlsstreamer.xml \
	hlsstreamer.glade

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
