if HAVE_EPYDOC

EPYDOC_HTML = html
EPYDOC_ARGS=-q --no-frames --html --ignore-param-mismatch

pypath=$(top_srcdir):@PYGTK_DIR@:$(PYTHONPATH)


MODULE_FILES = \
	flumotion/admin/__init__.py		\
	flumotion/admin/admin.py		\
	flumotion/common/__init__.py		\
	flumotion/common/auth.py		\
        flumotion/common/bundle.py		\
        flumotion/common/common.py		\
        flumotion/common/config.py		\
	flumotion/common/errors.py		\
	flumotion/common/interfaces.py		\
	flumotion/common/launcher.py		\
	flumotion/common/registry.py		\
	flumotion/component/__init__.py		\
	flumotion/component/component.py	\
	flumotion/configure/__init__.py		\
	flumotion/configure/configure.py	\
	flumotion/manager/__init__.py		\
	flumotion/manager/admin.py		\
	flumotion/manager/component.py		\
	flumotion/manager/manager.py		\
	flumotion/manager/worker.py		\
	flumotion/twisted/gstreactor.py		\
	flumotion/utils/gstutils.py		\
	flumotion/utils/log.py			\
	flumotion/worker/__init__.py		\
	flumotion/worker/worker.py		\
	flumotion/worker/job.py

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
