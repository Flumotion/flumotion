include $(top_srcdir)/common/python.mk
                                                                                
component_PYTHON = \
	__init__.py \
	jpeg/jpeg.py \
	mulaw/mulaw.py \
	smoke/smoke.py \
	speex/speex.py \
	theora/theora.py \
	vorbis/vorbis.py

componentdir = $(libdir)/flumotion/python/flumotion/component/encoders
component_DATA = encoders.xml

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
