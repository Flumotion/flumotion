include $(top_srcdir)/common/python.mk

flumotiondir = $(libdir)/flumotion/python/flumotion/extern

flumotion_PYTHON = \
	__init__.py \
	code.py \
	log/__init__.py \
	log/test_log.py \
	log/log.py

if BUILD_TRAYICON
PTI_DIR = pytrayicon
else
PTI_DIR =
endif

check-local:
	trial log.test_log

SUBDIRS = fdpass \
	$(PTI_DIR)

DIST_SUBDIRS = pytrayicon fdpass
