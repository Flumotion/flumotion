if HAVE_EPYDOC
EPYDOC_HTML = html
all-local:
	PYTHONPATH=$(PYTHONPATH):$(top_srcdir) epydoc \
            -q --no-frames --html \
		flumotion \
		flumotion.config \
		flumotion.admin flumotion.admin.spyglass

distclean-local:
	rm -rf html
else
EPYDOC_HTML =
endif
