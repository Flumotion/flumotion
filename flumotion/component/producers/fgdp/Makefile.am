include $(top_srcdir)/common/python.mk

fgdpdir = $(libdir)/flumotion/python/flumotion/component/producers/fgdp

fgdp_PYTHON = \
	__init__.py 	\
	fgdp.py

fgdp_DATA = fgdp.xml

TAGS_FILES = $(fgdp_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(fgdp_PYTHON) $(fgdp_DATA)
