include $(top_srcdir)/python.mk

SUBDIRS = \
	admin \
	common \
	component \
	configure \
	manager \
	service \
	test \
	tester \
	twisted \
	ui \
	utils \
	wizard \
	worker

flumotiondir = $(libdir)/flumotion/python/flumotion

flumotion_PYTHON = \
	__init__.py

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(flumotion_PYTHON) package.xml
