include $(top_srcdir)/common/python.mk

gdpdir = $(libdir)/flumotion/python/flumotion/component/consumers/gdp

gdp_PYTHON = \
	__init__.py 	\
	gdp.py \
	wizard.glade \
	wizard_gtk.py

gdp_DATA = gdp.xml

TAGS_FILES = $(gdp_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(gdp_PYTHON) $(gdp_DATA)
