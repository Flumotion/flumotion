if HAVE_EPYDOC

EPYDOC_HTML = html
EPYDOC_ARGS=-q --no-frames --html --ignore-param-mismatch

pypath=$(top_srcdir):@PYGTK_DIR@:$(PYTHONPATH)


MODULE_FILES = \
	flumotion/admin/__init__.py		\
	flumotion/admin/spyglass.py		\
	flumotion/config/__init__.py		\
	flumotion/common/errors.py		\
	flumotion/common/interfaces.py		\
	flumotion/component/component.py	\
	flumotion/component/base/producer.py	\
	flumotion/component/base/converter.py	\
	flumotion/component/file/file.py	\
	flumotion/component/http/http.py	\
	flumotion/component/passwd/passwd.py	\
	flumotion/manager/admin.py		\
	flumotion/manager/auth.py		\
        flumotion/manager/config.py		\
	flumotion/manager/manager.py		\
	flumotion/manager/launcher.py		\
	flumotion/manager/registry.py		\
	flumotion/twisted/gstreactor.py		\
	flumotion/utils/gstutils.py		\
	flumotion/utils/log.py

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
