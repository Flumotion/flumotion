include $(top_srcdir)/common/python.mk
                                                                                
consumersdir = $(libdir)/flumotion/python/flumotion/component/producers
consumers_PYTHON = \
	__init__.py checks.py
consumers_DATA = checks.xml

TAGS_FILES = $(component_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

SUBDIRS = \
	audiotest \
	bttv \
	firewire \
	icecast \
	pipeline \
	soundcard \
	videotest \
	webcam \
	looper \
	unixdomain \
	gdp

EXTRA_DIST = $(consumers_DATA)
