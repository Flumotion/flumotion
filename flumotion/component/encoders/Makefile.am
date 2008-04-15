include $(top_srcdir)/common/python.mk

componentdir = $(libdir)/flumotion/python/flumotion/component/encoders
component_PYTHON = \
	__init__.py

diracdir = $(componentdir)/dirac
dirac_PYTHON = \
	dirac/__init__.py \
	dirac/dirac.py \
	dirac/dirac_wizard.py
dirac_DATA = \
	dirac/dirac.xml \
	dirac/dirac-wizard.glade


jpegdir = $(componentdir)/jpeg
jpeg_PYTHON = \
	jpeg/__init__.py \
	jpeg/jpeg.py \
	jpeg/jpeg_wizard.py
jpeg_DATA = \
	jpeg/jpeg.xml \
	jpeg/jpeg-wizard.glade

mulawdir = $(componentdir)/mulaw
mulaw_PYTHON = \
	mulaw/__init__.py \
	mulaw/mulaw.py \
	mulaw/mulaw_wizard.py
mulaw_DATA = \
	mulaw/mulaw.xml \
	mulaw/mulaw-wizard.glade

smokedir = $(componentdir)/smoke
smoke_PYTHON = \
	smoke/__init__.py \
	smoke/smoke.py \
	smoke/smoke_wizard.py
smoke_DATA = \
	smoke/smoke.xml \
	smoke/smoke-wizard.glade

speexdir = $(componentdir)/speex
speex_PYTHON = \
	speex/__init__.py \
	speex/speex.py \
	speex/speex_wizard.py
speex_DATA = \
	speex/speex.xml

theoradir = $(componentdir)/theora
theora_PYTHON = \
	theora/__init__.py \
	theora/theora.py \
	theora/theora_wizard.py
theora_DATA = \
	theora/theora.xml \
	theora/theora-wizard.glade

vorbisdir = $(componentdir)/vorbis
vorbis_PYTHON = \
	vorbis/__init__.py \
	vorbis/vorbis.py \
	vorbis/vorbisutils.py \
	vorbis/vorbis010.py \
	vorbis/vorbis_wizard.py
vorbis_DATA = \
	vorbis/vorbis.xml \
	vorbis/vorbis-wizard.glade

clean-local:
	rm -rf *.pyc *.pyo */*.pyc */*.pyo

EXTRA_DIST = \
	$(component_DATA) \
	$(dirac_DATA) $(jpeg_DATA) $(mulaw_DATA) $(smoke_DATA) \
	$(speex_DATA) $(theora_DATA) $(vorbis_DATA)
