include $(top_srcdir)/python.mk
                                                                                
flumotiondir = $(libdir)/flumotion/python/flumotion/common

flumotion_PYTHON = \
	__init__.py \
	bundle.py \
	bundleclient.py \
	common.py \
	component.py \
	config.py \
	enum.py \
	errors.py \
	gstreamer.py \
	interfaces.py \
	log.py \
	keycards.py \
	planet.py \
	pygobject.py \
	registry.py \
	reload.py \
	setup.py \
	worker.py

TAGS_FILES = $(flumotion_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(flumotion_PYTHON)
