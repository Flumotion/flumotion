include $(top_srcdir)/common/python.mk

httpserverdir = $(libdir)/flumotion/python/flumotion/component/misc/httpserver

httpserver_PYTHON =		\
	__init__.py		\
	admin_gtk.py		\
	cachedprovider.py	\
	cachestats.py		\
	fileprovider.py		\
	httpfile.py		\
	httpserver.py		\
	localpath.py		\
	localprovider.py	\
	ratecontrol.py          \
	serverstats.py

httpserver_DATA = 		\
	httpfile.glade		\
	httpserver.xml 		\
	httpserver.glade

TAGS_FILES = $(httpserver_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(httpserver_PYTHON) $(httpserver_DATA)
