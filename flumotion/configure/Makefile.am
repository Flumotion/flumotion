include $(top_srcdir)/python.mk
                                                                                
INCLUDES = $(PYTHON_INCLUDES)

flumotiondir = $(libdir)/flumotion/python/flumotion/configure

flumotion_PYTHON = \
	__init__.py \
	configure.py \
	installed.py

noinst_PYTHON = uninstalled.py

TAGS_FILES = installed.py.in uninstalled.py.in

clean-local:
	rm -rf *.pyc *.pyo installed.py uninstalled.py

EXTRA_DIST = $(flumotion_PYTHON) installed.py.in uninstalled.py.in
