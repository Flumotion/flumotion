componentdir = $(libdir)/flumotion/python/flumotion/component/bouncers
component_PYTHON = \
	__init__.py \
	htpasswdcrypt.py \
	bouncer.py

component_DATA = htpasswdcrypt.xml

TAGS_FILES = $(component_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(component_DATA)
