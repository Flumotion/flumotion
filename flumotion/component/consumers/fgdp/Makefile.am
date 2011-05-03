include $(top_srcdir)/common/python.mk

fgdpdir = $(libdir)/flumotion/python/flumotion/component/consumers/fgdp

fgdp_PYTHON = \
	__init__.py 	\
	fgdp.py \
	wizard.glade \
	wizard_gtk.py

fgdp_DATA = fgdp.xml

TAGS_FILES = $(fgdp_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(fgdp_PYTHON) $(fgdp_DATA)
