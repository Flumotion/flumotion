flumotiondir = $(libdir)/flumotion/python/flumotion/common

flumotion_PYTHON = \
	__init__.py \
	auth.py \
	bundle.py \
	common.py \
	config.py \
	errors.py \
	interfaces.py \
	log.py \
	keycards.py \
	registry.py \
	setup.py

TAGS_FILES = $(flumotion_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(flumotion_DATA)
