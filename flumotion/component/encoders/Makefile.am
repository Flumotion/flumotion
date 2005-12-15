include $(top_srcdir)/common/python.mk
                                                                                
componentdir = $(libdir)/flumotion/python/flumotion/component/encoders
component_PYTHON = \
	__init__.py

jpegdir = $(componentdir)/jpeg
jpeg_PYTHON = \
	jpeg/__init__.py \
	jpeg/jpeg.py
jpeg_DATA = \
	jpeg/jpeg.xml

mulawdir = $(componentdir)/mulaw
mulaw_PYTHON = \
	mulaw/__init__.py \
	mulaw/mulaw.py
mulaw_DATA = \
	mulaw/mulaw.xml

smokedir = $(componentdir)/smoke
smoke_PYTHON = \
	smoke/__init__.py \
	smoke/smoke.py
smoke_DATA = \
	smoke/smoke.xml

speexdir = $(componentdir)/speex
speex_PYTHON = \
	speex/__init__.py \
	speex/speex.py
speex_DATA = \
	speex/speex.xml

theoradir = $(componentdir)/theora
theora_PYTHON = \
	theora/__init__.py \
	theora/theora.py
theora_DATA = \
	theora/theora.xml

vorbisdir = $(componentdir)/vorbis
vorbis_PYTHON = \
	vorbis/__init__.py \
	vorbis/vorbis.py \
	vorbis/vorbisutils.py \
	vorbis/vorbis08.py \
	vorbis/vorbis010.py
vorbis_DATA = \
	vorbis/vorbis.xml

clean-local:
	rm -rf *.pyc *.pyo */*.pyc */*.pyo

EXTRA_DIST = \
	$(component_DATA) \
	$(jpeg_DATA) $(mulaw_DATA) $(smoke_DATA) \
	$(speex_DATA) $(theora_DATA) $(vorbis_DATA)
