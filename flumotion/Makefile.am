include $(top_srcdir)/common/python.mk

SUBDIRS = \
	admin \
	common \
	component \
	configure \
	extern \
	job \
	launch \
	manager \
	monitor \
	project \
	service \
	test \
	tester \
	twisted \
	ui \
	worker

flumotiondir = $(libdir)/flumotion/python/flumotion

flumotion_PYTHON = \
	__init__.py
flumotion_DATA = package.xml

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(flumotion_DATA)
