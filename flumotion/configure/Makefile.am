include $(top_srcdir)/python.mk
                                                                                
INCLUDES = $(PYTHON_INCLUDES)

flumotiondir = $(libdir)/flumotion/python/flumotion/configure

flumotion_PYTHON = \
	__init__.py \
	configure.py \
	installed.py

noinst_PYTHON = uninstalled.py

BUILT_SOURCES = installed.py uninstalled.py

TAGS_FILES = installed.py.in uninstalled.py.in

DISTCLEAN_FILES = installed.pyc installed.pyo uninstalled.pyc uninstalled.pyo

EXTRA_DIST = $(flumotion_PYTHON) installed.py.in uninstalled.py.in
