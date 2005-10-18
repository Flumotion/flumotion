include $(top_srcdir)/common/python.mk

SUBDIRS = \
	admin \
	common \
	component \
	configure \
	extern \
	launch \
	manager \
	project \
	service \
	test \
	tester \
	twisted \
	ui \
	wizard \
	worker

flumotiondir = $(libdir)/flumotion/python/flumotion

flumotion_PYTHON = \
	__init__.py
flumotion_DATA = package.xml
 
clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(flumotion_DATA)
