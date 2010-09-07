include $(top_srcdir)/common/python.mk

component_PYTHON = __init__.py audiorate.py
componentdir = $(libdir)/flumotion/python/flumotion/component/effects/audiorate
component_DATA = audiorate.xml

clean-local:
	rm -rf *.pyc *.pyo

# PYCHECKER_FILES = $(component_PYTHON)

EXTRA_DIST = $(component_DATA)
