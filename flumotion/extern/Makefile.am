include $(top_srcdir)/common/python.mk

flumotiondir = $(libdir)/flumotion/python/flumotion/extern

flumotion_PYTHON = 	\
	__init__.py 	\
	code.py		\
	exceptiondialog.py
	unixcrypt.py

logdir = $(libdir)/flumotion/python/flumotion/extern/log

log_PYTHON = \
	log/__init__.py \
	log/log.py \
	log/termcolor.py

commanddir = $(libdir)/flumotion/python/flumotion/extern/command

command_PYTHON = \
	command/__init__.py \
	command/command.py

EXTRA_DIST = log/test_log.py

if BUILD_TRAYICON
PTI_DIR = pytrayicon
else
PTI_DIR =
endif

check-local:
	PYTHONPATH=$(srcdir):$$PYTHONPATH trial log.test_log

clean-local:
	rm -rf _trial_temp

SUBDIRS = fdpass \
	$(PTI_DIR)

DIST_SUBDIRS = pytrayicon fdpass
