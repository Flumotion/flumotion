include $(top_srcdir)/common/python.mk

componentdir = $(libdir)/flumotion/python/flumotion/admin/gtk
component_PYTHON = 			\
	__init__.py 			\
	addformatassistant.py 		\
	adminwindow.py 			\
	connections.py 			\
	componentlist.py 		\
	componentview.py 		\
	configurationassistant.py 	\
	debugmarkerview.py 		\
	dialogs.py 			\
	greeter.py 			\
	message.py 			\
	main.py 			\
	statusbar.py

all-local:
	if test -e videotest.pyc; then rm videotest.pyc; fi

clean-local:
	rm -rf *.pyc *.pyo
