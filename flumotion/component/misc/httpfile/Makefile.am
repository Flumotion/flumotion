include $(top_srcdir)/common/python.mk

httpfiledir = $(libdir)/flumotion/python/flumotion/component/misc/httpfile

httpfile_PYTHON = \
	__init__.py 	\
	httpfile.py	\
	file.py         \
	admin_gtk.py

httpfile_DATA = httpfile.xml

TAGS_FILES = $(httpfile_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(httpfile_PYTHON) $(httpfile_DATA) httpfile.glade
