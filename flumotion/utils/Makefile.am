INCLUDES = $(PYTHON_INCLUDES)

flumotiondir = $(libdir)/flumotion/python/flumotion/utils

flumotion_DATA = \
	gstutils.py \
	__init__.py \
	log.py

pkgpyexec_LTLIBRARIES = _proctitle.la

_proctitle_la_LDFLAGS = -module -avoid-version -export-symbols-regex init_proctitle
_proctitle_la_SOURCES = _proctitle.c

EXTRA_DIST = $(flumotion_DATA)
