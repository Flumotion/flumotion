include $(top_srcdir)/common/python.mk

component_PYTHON = __init__.py pipeline.py
componentdir = $(libdir)/flumotion/python/flumotion/component/producers/pipeline
component_DATA = pipeline.xml

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
