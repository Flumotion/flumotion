INCLUDES = $(PYTHON_INCLUDES)

flumotiondir = $(libdir)/flumotion/python/flumotion/config

flumotion_PYTHON = \
	__init__.py \
	installed.py
noinst_PYTHON = uninstalled.py

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(flumotion_DATA) installed.py.in uninstalled.py.in
