include $(top_srcdir)/common/python.mk

porterdir = $(libdir)/flumotion/python/flumotion/porter

porter_PYTHON = \
	__init__.py 	\
	porterclient.py \
	porter.py

porter_DATA = porter.xml

TAGS_FILES = $(porter_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(porter_PYTHON) $(porter_DATA)
