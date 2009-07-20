if HAVE_EPYDOC

EPYDOC_HTML = html
EPYDOC_ARGS = -q --no-frames --html

MODULES = $(subst /,.,$(patsubst %.py,%, $(MODULE_FILES:/__init__.py=)))

# misc is in builddir
pypath = $(top_builddir):$(top_srcdir):$(PYTHONPATH)

html/index.html: $(patsubst %, $(top_srcdir)/%, $(MODULE_FILES)) $(top_srcdir)/common/gendoc.py
	@echo Generating HTML documentation...
	@$(PYTHON) -c "import os; print os.getpid() + 10" > display
	@Xvfb -ac :`cat display` & echo $$! > Xvfb.pid
	DISPLAY=:`cat display` PYTHONPATH=$(FLUMOTION_DIR):$(pypath) $(PYTHON) $(top_srcdir)/common/gendoc.py $(EPYDOC_ARGS) $(MODULES) 2>&1; echo $$? > ret
	@kill `cat Xvfb.pid`
	@rm Xvfb.pid display
	@exit `cat ret; rm -f ret`
# FIXME: this stopped working when running with Xvfb, but no idea why
# we need to look at newer epydoc anyway
#| $(PYTHON) $(top_srcdir)/common/filterdoc.py

all-local-epydoc: html/index.html

check-local-epydoc:
	@PYTHONPATH=$(pypath) $(PYTHON) $(top_srcdir)/common/gendoc.py --check $(MODULES) 2>&1 | $(PYTHON) $(top_srcdir)/common/filterdoc.py

clean-local-epydoc:
	rm -rf html
	-rm Xvfb.pid
else
EPYDOC_HTML =
all-local-epydoc:
	true

check-local-epydoc:
	true

clean-local-epydoc:
	true
endif
