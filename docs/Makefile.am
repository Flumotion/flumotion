if HAVE_EPYDOC
EPYDOC_HTML = html
all-local:
	export PYTHONPATH=$(PYTHONPATH):$(top_srcdir); epydoc -q --no-frames --html flumotion
distclean-local:
	rm -rf html
else
EPYDOC_HTML =
endif
