include $(top_srcdir)/common/python.mk

componentdir = $(libdir)/flumotion/python/flumotion/component/base
component_DATA = 		\
	base.xml 		\
	feeders.glade 		\
	eaters.glade 		\
	component.glade 	\
	properties.glade
component_PYTHON = __init__.py 	\
	admin_gtk.py 		\
	admin_text.py 		\
	baseadminnode.py 	\
	componentnode.py 	\
	eatersnode.py 		\
	effectsnode.py 		\
	feedersnode.py 		\
	http.py 		\
	multiple.py 		\
	propertiesnode.py 	\
	scheduler.py 		\
	statewatcher.py		\
	watcher.py


clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
