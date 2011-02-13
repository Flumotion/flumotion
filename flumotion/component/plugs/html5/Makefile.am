include $(top_srcdir)/common/python.mk

html5dir = $(libdir)/flumotion/python/flumotion/component/plugs/html5

html5_PYTHON = 		\
	__init__.py 		\
	html5.py 		\
	wizard_gtk.py

html5_DATA = html5.xml

TAGS_FILES = $(html5_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(html5_PYTHON) $(html5_DATA)
