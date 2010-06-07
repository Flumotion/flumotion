include $(top_srcdir)/common/python.mk

component_PYTHON = __init__.py genimg.py overlay.py
componentdir = $(libdir)/flumotion/python/flumotion/component/converters/overlay
component_DATA = \
	overlay.xml 		\
	cc.24x24.png 		\
	fluendo.24x24.png 	\
	xiph.24x24.png		\
	cc.36x36.png 		\
	fluendo.36x36.png 	\
	xiph.36x36.png

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
