if HAVE_EPYDOC
EPYDOC_HTML = html
pypath=$(PYTHONPATH):@PYGTK_DIR@:$(top_srcdir):.
EPYDOC_ARGS=-q --no-frames --html --ignore-param-mismatch
MODULES = \
	flumotion.admin \
	flumotion.admin.spyglass \
	flumotion.components.converter \
 	flumotion.components.file \
	flumotion.components.http \
	flumotion.components.producer \
	flumotion.config \
	flumotion.errors \
	flumotion.server.admin \
	flumotion.server.component \
        flumotion.server.config \
	flumotion.server.controller \
	flumotion.server.errors \
	flumotion.server.launcher \
	flumotion.server.registry \
	flumotion.twisted.gstreactor \
	flumotion.utils.gstutils \
	flumotion.utils.log

all-local:
	@echo Generating HTML documentation...
	@PYTHONPATH=$(pypath) $(PYTHON) gendoc.py $(EPYDOC_ARGS) $(MODULES)
distclean-local:
	rm -rf html
else
EPYDOC_HTML =
endif
