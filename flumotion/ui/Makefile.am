include $(top_srcdir)/python.mk
                                                                                
flumotiondir = $(libdir)/flumotion/python/flumotion/ui

flumotion_PYTHON = \
	__init__.py \
	fgtk.py \
	glade.py \
	icons.py

TAGS_FILES = $(flumotion_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(flumotion_PYTHON)
