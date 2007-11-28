include $(top_srcdir)/common/python.mk

flumotiondir = $(libdir)/flumotion/python/flumotion/ui

flumotion_PYTHON = 	\
	__init__.py 	\
	fgtk.py 	\
	fvumeter.py 	\
	glade.py 	\
	icons.py 	\
	trayicon.py 	\
	url.py		\
	wizard.py

TAGS_FILES = $(flumotion_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(flumotion_PYTHON)
