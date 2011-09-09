include $(top_srcdir)/common/python.mk

component_PYTHON = __init__.py kuscheduler.py
componentdir = $(libdir)/flumotion/python/flumotion/component/effects/kuscheduler
component_DATA = kuscheduler.xml

clean-local:
	rm -rf *.pyc *.pyo

# PYCHECKER_FILES = $(component_PYTHON)

EXTRA_DIST = $(component_DATA)
