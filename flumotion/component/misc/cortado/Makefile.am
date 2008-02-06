include $(top_srcdir)/common/python.mk

cortadodir = $(libdir)/flumotion/python/flumotion/component/misc/cortado

cortado_PYTHON = \
	__init__.py 	\
	cortado.py

cortado_DATA = cortado.xml cortado_location.py.in

TAGS_FILES = $(cortado_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(cortado_PYTHON) $(cortado_DATA)
