include $(top_srcdir)/common/python.mk

fgdpdir = $(libdir)/flumotion/python/flumotion/component/common/fgdp
fgdp_DATA = fgdp.xml
fgdp_PYTHON = \
	__init__.py \
	fgdp.py \
	protocol.py

TAGS_FILES = $(fgdp_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(fgdp_DATA) $(fgdp_PYTHON)
