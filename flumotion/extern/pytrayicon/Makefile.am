include $(top_srcdir)/common/python.mk
                                                                                
flumotiondir = $(libdir)/flumotion/python/flumotion/extern/pytrayicon

flumotion_PYTHON = \
	__init__.py

CLEANFILES = pytrayicon.c

noinst_HEADERS = config.h eggtrayicon.h

flumotion_LTLIBRARIES = pytrayicon.la
pytrayicon_la_SOURCES = eggtrayicon.c pytrayiconmodule.c pytrayicon.c
pytrayicon_la_CFLAGS = $(PYGTK_CFLAGS) $(PYTHON_INCLUDES) $(GTK_CFLAGS)
pytrayicon_la_LIBADD = $(GTK_LIBS)
pytrayicon_la_LDFLAGS = -module -avoid-version

pytrayicon.c: pytrayicon.defs pytrayicon.override
	(cd $(srcdir) \
	&& $(PYGTK_CODEGEN) \
		--prefix pytrayicon \
		--register $(PYGTK_DEFSDIR)/gdk-types.defs \
		--register $(PYGTK_DEFSDIR)/gtk-types.defs \
		--override pytrayicon.override \
		pytrayicon.defs > $@)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(flumotion_PYTHON) pytrayicon.defs pytrayicon.override \
	eggtrayicon.c eggtrayicon.h pytrayiconmodule.c
