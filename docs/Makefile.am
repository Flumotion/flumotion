if HAVE_EPYDOC
EPYDOC_HTML = html
pypath=$(PYTHONPATH):@PYGTK_DIR@:$(top_srcdir):.
EPYDOC_ARGS=-q --no-frames --html --ignore-param-mismatch
MODULES = \
	flumotion.config \
	flumotion.server.config \
	flumotion.server.controller \
	flumotion.server.component \
	flumotion.server.launcher \
	flumotion.components.http
all-local:
	PYTHONPATH=$(pypath) $(PYTHON) gendoc.py $(EPYDOC_ARGS) $(MODULES)
distclean-local:
	rm -rf html
else
EPYDOC_HTML =
endif
