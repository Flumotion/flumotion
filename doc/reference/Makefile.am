include $(top_srcdir)/common/epydoc.mk

MODULE_FILES = $(shell cd $(top_srcdir) && ls		\
	flumotion/admin/*.py				\
	flumotion/common/*.py				\
	flumotion/component/*.py			\
	flumotion/component/base/*.py			\
	flumotion/component/bouncers/__init__.py	\
	flumotion/configure/__init__.py			\
	flumotion/configure/configure.py		\
	flumotion/extern/*.py				\
	flumotion/job/*.py				\
	flumotion/launch/*.py				\
	flumotion/manager/*.py				\
	flumotion/project/*.py				\
	flumotion/service/*.py				\
	flumotion/twisted/*.py				\
	flumotion/worker/*.py				\
	flumotion/worker/checks/*.py			\
	)

# FIXME: add these when we find a way to deal with epydoc spew
#	flumotion/ui/*.py
#	flumotion/wizard/*.py

check-local: check-local-epydoc

all-local: all-local-epydoc

clean-local: clean-local-epydoc
