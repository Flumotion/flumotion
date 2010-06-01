include $(top_srcdir)/common/python.mk

componentdir = $(libdir)/flumotion/python/flumotion/component/encoders
component_PYTHON = \
	__init__.py

diracdir = $(componentdir)/dirac
dirac_PYTHON = \
	dirac/__init__.py \
	dirac/dirac.py \
	dirac/wizard_gtk.py
dirac_DATA = \
	dirac/dirac.xml \
	dirac/wizard.glade


jpegdir = $(componentdir)/jpeg
jpeg_PYTHON = \
	jpeg/__init__.py \
	jpeg/jpeg.py \
	jpeg/wizard_gtk.py
jpeg_DATA = \
	jpeg/jpeg.xml \
	jpeg/wizard.glade

mulawdir = $(componentdir)/mulaw
mulaw_PYTHON = \
	mulaw/__init__.py \
	mulaw/mulaw.py \
	mulaw/wizard_gtk.py
mulaw_DATA = \
	mulaw/mulaw.xml \
	mulaw/wizard.glade

smokedir = $(componentdir)/smoke
smoke_PYTHON = \
	smoke/__init__.py \
	smoke/smoke.py \
	smoke/wizard_gtk.py
smoke_DATA = \
	smoke/smoke.xml \
	smoke/wizard.glade

speexdir = $(componentdir)/speex
speex_PYTHON = \
	speex/__init__.py \
	speex/speex.py \
	speex/wizard_gtk.py
speex_DATA = \
	speex/speex.xml

theoradir = $(componentdir)/theora
theora_PYTHON = \
	theora/__init__.py \
	theora/theora.py \
	theora/wizard_gtk.py
theora_DATA = \
	theora/theora.xml \
	theora/wizard.glade

vorbisdir = $(componentdir)/vorbis
vorbis_PYTHON = \
	vorbis/__init__.py \
	vorbis/vorbis.py \
	vorbis/vorbisutils.py \
	vorbis/vorbis010.py \
	vorbis/wizard_gtk.py
vorbis_DATA = \
	vorbis/vorbis.xml \
	vorbis/wizard.glade

vp8dir = $(componentdir)/vp8
vp8_PYTHON = \
	vp8/__init__.py \
	vp8/vp8.py \
	vp8/wizard_gtk.py
vp8_DATA = \
	vp8/vp8.xml \
	vp8/wizard.glade

clean-local:
	rm -rf *.pyc *.pyo */*.pyc */*.pyo

EXTRA_DIST = \
	$(component_DATA) \
	$(dirac_DATA) $(jpeg_DATA) $(mulaw_DATA) $(smoke_DATA) \
	$(speex_DATA) $(theora_DATA) $(vorbis_DATA)
