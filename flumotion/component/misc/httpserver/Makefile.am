include $(top_srcdir)/common/python.mk

SUBDIRS = httpcached

httpserverdir = $(libdir)/flumotion/python/flumotion/component/misc/httpserver

httpserver_PYTHON =		\
	__init__.py		\
	admin_gtk.py		\
	cachemanager.py	\
	cachedprovider.py	\
	cachestats.py		\
	fileprovider.py		\
	httpfile.py		\
	httpserver.py		\
	localpath.py		\
	localprovider.py	\
	ondemandbrowser.py	\
	ratecontrol.py          \
	serverstats.py		\
	metadataprovider.py \
	mimetypes.py

httpserver_DATA = 		\
	httpfile.glade		\
	httpserver.xml 		\
	httpserver.glade

TAGS_FILES = $(httpserver_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(httpserver_PYTHON) $(httpserver_DATA)
