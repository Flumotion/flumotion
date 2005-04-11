include $(top_srcdir)/common/python.mk
                                                                                
flumotiondir = $(libdir)/flumotion/python/flumotion/configure

flumotion_PYTHON = \
	__init__.py \
	configure.py \
	installed.py

noinst_PYTHON = uninstalled.py

BUILT_SOURCES = installed.py uninstalled.py

TAGS_FILES = installed.py.in uninstalled.py.in

DISTCLEANFILES = installed.pyc installed.pyo uninstalled.pyc uninstalled.pyo

EXTRA_DIST = $(flumotion_PYTHON) installed.py.in uninstalled.py.in
