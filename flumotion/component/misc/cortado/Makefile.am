include $(top_srcdir)/common/python.mk

cortadodir = $(libdir)/flumotion/python/flumotion/component/misc/cortado

cortado_PYTHON = 		\
	__init__.py 		\
	cortado.py 		\
	cortado_location.py 	\
	cortado_wizard.py 

cortado_DATA = cortado.xml

TAGS_FILES = $(cortado_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(cortado_PYTHON) $(cortado_DATA)
