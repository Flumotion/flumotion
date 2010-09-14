include $(top_srcdir)/common/python.mk

componentdir = $(libdir)/flumotion/python/flumotion/admin/gtk
component_PYTHON =			\
       __init__.py \
       about.py \
       adminwindow.py \
       basesteps.py \
       componentlist.py \
       componentview.py \
       configurationassistant.py \
       connections.py \
       debugmarkerview.py \
       dialogs.py \
       greeter.py \
       main.py \
       message.py \
       overlaystep.py \
       statusbar.py \
       workerlist.py \
       workerstep.py 

all-local:
	if test -e videotest.pyc; then rm videotest.pyc; fi

clean-local:
	rm -rf *.pyc *.pyo
