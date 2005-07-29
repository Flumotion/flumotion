$(PROJECT).locale.xml: $(top_srcdir)/po/LINGUAS $(top_srcdir)/common/gen-locale-xml.py
	$(PYTHON) $(top_srcdir)/common/gen-locale-xml.py \
                $(GETTEXT_PACKAGE) $(PROJECT) `cat $(top_srcdir)/po/LINGUAS` > $@
