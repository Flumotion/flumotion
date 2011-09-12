include $(top_srcdir)/common/python.mk

streamerdir = $(libdir)/flumotion/python/flumotion/component/common/streamer
streamer_DATA = streamer.xml streamer.glade properties.xml
streamer_PYTHON = \
	__init__.py \
	streamer.py \
	resources.py \
	admin_gtk.py

TAGS_FILES = $(avproducer_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(streamer_DATA) $(streamer_PYTHON)
