include $(top_srcdir)/common/python.mk

flumotiondir = $(libdir)/flumotion/python/flumotion/launch

flumotion_PYTHON = \
	__init__.py 	\
	inspect.py \
	main.py

TAGS_FILES = $(flumotion_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(flumotion_PYTHON)
