if HAVE_EPYDOC
EPYDOC_HTML = html
pypath=$(PYTHONPATH):@PYGTK_DIR@:$(top_srcdir):.
EPYDOC_ARGS=-q --no-frames --html --ignore-param-mismatch
MODULE_FILES = \
	flumotion/admin/__init__.py		\
	flumotion/admin/spyglass.py		\
	flumotion/components/converter.py	\
 	flumotion/components/file.py		\
	flumotion/components/http.py		\
	flumotion/components/producer.py	\
	flumotion/components/passwd.py		\
	flumotion/config/__init__.py		\
	flumotion/errors.py			\
	flumotion/server/admin.py		\
	flumotion/server/auth.py		\
	flumotion/server/component.py		\
        flumotion/server/config.py		\
	flumotion/server/controller.py		\
	flumotion/server/errors.py		\
	flumotion/server/interfaces.py		\
	flumotion/server/launcher.py		\
	flumotion/server/registry.py		\
	flumotion/twisted/gstreactor.py		\
	flumotion/utils/gstutils.py		\
	flumotion/utils/log.py

MODULES = $(subst /,.,$(patsubst %.py,%, $(MODULE_FILES:/__init__.py=)))

html/index.html: $(patsubst %, $(top_srcdir)/%, $(MODULE_FILES))
	@echo Generating HTML documentation...
	@PYTHONPATH=$(pypath) $(PYTHON) gendoc.py $(EPYDOC_ARGS) $(MODULES)

all-local: html/index.html

clean-local:
	rm -rf html
else
EPYDOC_HTML =
endif
