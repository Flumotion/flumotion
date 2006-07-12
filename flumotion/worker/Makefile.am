include $(top_srcdir)/common/python.mk

SUBDIRS = checks

flumotiondir = $(libdir)/flumotion/python/flumotion/worker

flumotion_PYTHON = \
	__init__.py 	\
	config.py 	\
	feed.py 	\
	main.py 	\
	worker.py

TAGS_FILES = $(flumotion_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(flumotion_PYTHON)
