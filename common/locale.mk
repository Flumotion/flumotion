$(PROJECT).locale.xml: $(top_srcdir)/po/LINGUAS
	$(PYTHON) $(top_srcdir)/common/gen-locale-xml.py \
                $(GETTEXT_PACKAGE) $(PROJECT) `cat $(top_srcdir)/po/LINGUAS` > $@
