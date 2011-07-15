include $(top_srcdir)/common/python.mk

avproducerdir = $(libdir)/flumotion/python/flumotion/component/common/avproducer
avproducer_DATA = avproducer.xml
avproducer_PYTHON = \
	__init__.py \
	avproducer.py \
	admin_gtk.py

TAGS_FILES = $(avproducer_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(avproducer_DATA) $(avproducer_PYTHON)
