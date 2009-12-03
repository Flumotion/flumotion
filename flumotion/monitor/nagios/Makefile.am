include $(top_srcdir)/common/python.mk

flumotiondir = $(libdir)/flumotion/python/flumotion/monitor/nagios

flumotion_PYTHON =	\
	__init__.py	\
	log.py		\
	util.py		\
	main.py 	\
	process.py	\
	stream.py	\
	component.py

TAGS_FILES = $(flumotion_PYTHON)
ETAGS_ARGS = --lang=python $(flumotion_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(flumotion_PYTHON)
