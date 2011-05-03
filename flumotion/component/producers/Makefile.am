include $(top_srcdir)/common/python.mk

producersdir = $(libdir)/flumotion/python/flumotion/component/producers
producers_PYTHON = \
	__init__.py checks.py
producers_DATA = checks.xml

TAGS_FILES = $(component_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

SUBDIRS = \
	audiotest \
	bttv \
	firewire \
	icecast \
	ivtv \
	pipeline \
	playlist \
	rtsp \
	screencast \
	soundcard \
	videotest \
	webcam \
	looper \
	unixdomain \
	fgdp

EXTRA_DIST = $(producers_DATA)
