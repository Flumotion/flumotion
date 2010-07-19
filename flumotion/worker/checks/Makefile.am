include $(top_srcdir)/common/python.mk

flumotiondir = $(libdir)/flumotion/python/flumotion/worker/checks

flumotion_PYTHON = \
	__init__.py 	\
	check.py	\
	encoder.py	\
	video.py	\
	gst010.py	\
	audio.py	\
	device.py       \
	cortado.py	\
	http.py	        \
	package.xml

TAGS_FILES = $(flumotion_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(flumotion_PYTHON)
