include $(top_srcdir)/common/python.mk

componentdir = $(libdir)/flumotion/python/flumotion/admin/gtk
component_PYTHON = 			\
	__init__.py 			\
	addformatassistant.py 		\
	adminwindow.py 			\
	basesteps.py 			\
	connections.py 			\
	consumptionsteps.py		\
	conversionsteps.py		\
	componentlist.py 		\
	componentview.py 		\
	configurationassistant.py 	\
	debugmarkerview.py 		\
	dialogs.py 			\
	diskersteps.py			\
	greeter.py 			\
	httpstreamersteps.py		\
	message.py 			\
	main.py 			\
	ondemandstep.py			\
	overlaysteps.py			\
	productionsteps.py		\
	shout2steps.py			\
	statusbar.py			\
	workerlist.py			\
	workerstep.py

all-local:
	if test -e videotest.pyc; then rm videotest.pyc; fi

clean-local:
	rm -rf *.pyc *.pyo
