include $(top_srcdir)/common/python.mk

flumotiondir = $(libdir)/flumotion/python/flumotion/ui

flumotion_PYTHON = 	\
	__init__.py 	\
	fgtk.py 	\
	fileselector.py	\
	fvumeter.py 	\
	glade.py 	\
	kiwipatches.py 	\
	linkwidget.py 	\
	icons.py 	\
	sidebar.py 	\
	simplewizard.py \
	trayicon.py 	\
	wizard.py

TAGS_FILES = $(flumotion_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(flumotion_PYTHON)
