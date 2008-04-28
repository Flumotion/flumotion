include $(top_srcdir)/common/python.mk

flumotiondir = $(libdir)/flumotion/python/flumotion/common

flumotion_PYTHON = \
	__init__.py \
	avltree.py \
	boot.py \
	bundle.py \
	bundleclient.py \
	connection.py \
	common.py \
	componentui.py \
	config.py \
	dag.py \
	debug.py \
	documentation.py \
	enum.py \
	errors.py \
	fxml.py \
	gstreamer.py \
	identity.py \
	interfaces.py \
	log.py \
	keycards.py \
	manhole.py \
	medium.py \
	messages.py \
	netutils.py \
	options.py \
	package.py \
	planet.py \
	pygobject.py \
	python.py \
	reflectcall.py \
	registry.py \
	reload.py \
	server.py \
	setup.py \
	signals.py \
	startset.py \
	testsuite.py \
	watched.py \
	worker.py \
	xmlwriter.py

TAGS_DEPENDENCIES = $(flumotion_PYTHON)
ETAGS_ARGS = --lang=python $(flumotion_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo
