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
flumotion_DATA = package.xml
 
clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(flumotion_DATA)
