include $(top_srcdir)/python.mk
                                                                                
component_PYTHON = \
	__init__.py \
	multipart.py \
	ogg.py

componentdir = $(libdir)/flumotion/python/flumotion/component/muxers
component_DATA = muxers.xml

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
