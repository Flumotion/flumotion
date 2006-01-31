include $(top_srcdir)/common/python.mk

flumotiondir = $(libdir)/flumotion/python/flumotion/worker/checks

flumotion_PYTHON = \
	__init__.py 	\
	check.py	\
	encoder.py	\
	video.py	\
	video08.py	\
	video010.py	\
	package.xml

TAGS_FILES = $(flumotion_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(flumotion_PYTHON)
