include $(top_srcdir)/common/python.mk
                                                                                
component_PYTHON = __init__.py admin_gtk.py admin_text.py http.py
componentdir = $(libdir)/flumotion/python/flumotion/component/base
component_DATA = base.xml

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
