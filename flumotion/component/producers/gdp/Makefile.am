include $(top_srcdir)/common/python.mk

gdpdir = $(libdir)/flumotion/python/flumotion/component/producers/gdp

gdp_PYTHON = \
	__init__.py 	\
	gdp.py

gdp_DATA = gdp.xml

TAGS_FILES = $(gdp_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(gdp_PYTHON) $(gdp_DATA)
