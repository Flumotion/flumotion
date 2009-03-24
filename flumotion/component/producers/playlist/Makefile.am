include $(top_srcdir)/common/python.mk

component_PYTHON = __init__.py playlist.py singledecodebin.py smartscale.py \
	playlistparser.py
componentdir = $(libdir)/flumotion/python/flumotion/component/producers/playlist
component_DATA = playlist.xml

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA) playlist.dtd
