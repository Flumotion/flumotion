include $(top_srcdir)/common/python.mk
                                                                                
miscdir = $(libdir)/flumotion/python/flumotion/component/misc
misc_PYTHON = \
	__init__.py

TAGS_FILES = $(misc_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

SUBDIRS = \
	porter \
	repeater \
	httpfile

EXTRA_DIST = $(misc_DATA)
