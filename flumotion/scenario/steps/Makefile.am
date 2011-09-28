include $(top_srcdir)/common/python.mk

componentdir = $(libdir)/flumotion/python/flumotion/scenario/steps
component_PYTHON = \
	__init__.py \
	consumptionsteps.py \
	conversionsteps.py \
	loadflowstep.py \
	ondemandstep.py \
	productionsteps.py \
	summarysteps.py

component_DATA = \
	steps.xml

TAGS_FILES = $(component_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
