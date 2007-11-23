include $(top_srcdir)/common/python.mk

componentdir = $(libdir)/flumotion/python/flumotion/admin/gtk
component_PYTHON = \
	__init__.py \
	client.py \
	connections.py \
	componentview.py \
	dialogs.py \
	greeter.py \
	message.py \
	parts.py \
	main.py \
	spyglass.py \
	wizard.py

all-local:
	if test -e videotest.pyc; then rm videotest.pyc; fi

clean-local:
	rm -rf *.pyc *.pyo
