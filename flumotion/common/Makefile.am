include $(top_srcdir)/common/python.mk
                                                                                
flumotiondir = $(libdir)/flumotion/python/flumotion/common

BUILT_SOURCES = boot.py

nodist_flumotion_PYTHON = \
	boot.py

flumotion_PYTHON = \
	__init__.py \
	boot.py \
	bundle.py \
	bundleclient.py \
	code.py \
	common.py \
	compat.py \
	componentui.py \
	config.py \
	dag.py \
	debug.py \
	enum.py \
	errors.py \
	gstreamer.py \
	interfaces.py \
	log.py \
	keycards.py \
	medium.py \
	package.py \
	planet.py \
	pygobject.py \
	registry.py \
	reload.py \
	setup.py \
	watched.py \
	worker.py

TAGS_DEPENDENCIES = $(flumotion_PYTHON)
ETAGS_ARGS = --lang=python $(flumotion_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = boot.py.in
