if HAVE_EPYDOC

EPYDOC_HTML = html
EPYDOC_ARGS=-q --no-frames --html --ignore-param-mismatch

pypath=$(top_srcdir):@PYGTK_DIR@:$(PYTHONPATH)

MODULE_FILES = $(shell cd $(top_srcdir) && ls		\
	flumotion/admin/*.py				\
	flumotion/common/*.py				\
	flumotion/component/*.py			\
	flumotion/component/base/*.py			\
	flumotion/component/bouncers/__init__.py	\
	flumotion/component/bouncers/bouncer.py		\
	flumotion/configure/__init__.py			\
	flumotion/configure/configure.py		\
	flumotion/manager/*.py				\
	flumotion/twisted/*.py				\
	flumotion/worker/*.py				\
	flumotion/worker/checks/*.py			\
	)

MODULES = $(subst /,.,$(patsubst %.py,%, $(MODULE_FILES:/__init__.py=)))

html/index.html: $(patsubst %, $(top_srcdir)/%, $(MODULE_FILES)) gendoc.py
	@echo Generating HTML documentation...
	@PYTHONPATH=$(pypath) $(PYTHON) $(srcdir)/gendoc.py $(EPYDOC_ARGS) $(MODULES)

check-local:
	@PYTHONPATH=$(pypath) $(PYTHON) $(srcdir)/gendoc.py --check $(MODULES)

all-local: html/index.html

clean-local:
	rm -rf html
else
EPYDOC_HTML =
endif

EXTRA_DIST = gendoc.py
