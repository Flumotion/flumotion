include $(top_srcdir)/common/python.mk

component_PYTHON = __init__.py \
	admin_gtk.py \
	admin_text.py \
	baseadminnode.py \
	componentnode.py \
	eatersnode.py \
	effectsnode.py \
	feedersnode.py \
	http.py \
	scheduler.py \
	statewatcher.py	\
	watcher.py

componentdir = $(libdir)/flumotion/python/flumotion/component/base
component_DATA = base.xml feeders.glade eaters.glade component.glade

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
