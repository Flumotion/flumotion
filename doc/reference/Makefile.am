if HAVE_EPYDOC

EPYDOC_HTML = html
EPYDOC_ARGS=-q --no-frames --html --ignore-param-mismatch

pypath=$(top_srcdir):@PYGTK_DIR@:$(PYTHONPATH)


MODULE_FILES = \
	flumotion/admin/__init__.py		\
	flumotion/admin/spyglass.py		\
	flumotion/config/__init__.py		\
	flumotion/components/base/producer.py	\
	flumotion/components/base/converter.py	\
	flumotion/components/file/file.py	\
	flumotion/components/http/http.py	\
	flumotion/components/passwd/passwd.py	\
	flumotion/errors.py			\
	flumotion/server/admin.py		\
	flumotion/server/auth.py		\
	flumotion/server/component.py		\
        flumotion/server/config.py		\
	flumotion/server/manager.py		\
	flumotion/server/interfaces.py		\
	flumotion/server/launcher.py		\
	flumotion/server/registry.py		\
	flumotion/twisted/gstreactor.py		\
	flumotion/twisted/errors.py		\
	flumotion/utils/gstutils.py		\
	flumotion/utils/log.py

MODULES = $(subst /,.,$(patsubst %.py,%, $(MODULE_FILES:/__init__.py=)))

html/index.html: $(patsubst %, $(top_srcdir)/%, $(MODULE_FILES)) gendoc.py
	@echo Generating HTML documentation...
	@PYTHONPATH=$(pypath) $(PYTHON) $(srcdir)/gendoc.py $(EPYDOC_ARGS) $(MODULES)

check-local:
	PYTHONPATH=$(pypath) $(PYTHON) $(srcdir)/gendoc.py --check $(MODULES)
	
all-local: html/index.html

clean-local:
	rm -rf html
else
EPYDOC_HTML =
endif

EXTRA_DIST = gendoc.py
