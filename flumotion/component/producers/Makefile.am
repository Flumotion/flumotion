include $(top_srcdir)/common/python.mk
                                                                                
consumersdir = $(libdir)/flumotion/python/flumotion/component/producers
consumers_PYTHON = \
	__init__.py

TAGS_FILES = $(component_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

SUBDIRS = \
	audiotest \
	bttv \
	firewire \
	pipeline \
	soundcard \
	videotest \
	webcam \
	jukebox \
	looper
