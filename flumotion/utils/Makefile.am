INCLUDES = $(PYTHON_INCLUDES)

flumotiondir = $(libdir)/flumotion/python/flumotion/utils

flumotion_PYTHON = \
	__init__.py \
	gstutils.py \
	log.py \
	reload.py

TAGS_FILES = $(flumotion_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(flumotion_DATA)
