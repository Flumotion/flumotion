include $(top_srcdir)/common/python.mk

unixdomaindir = $(libdir)/flumotion/python/flumotion/component/producers/unixdomain

unixdomain_PYTHON = \
	__init__.py 	\
	unixdomain.py

unixdomain_DATA = unixdomain.xml

TAGS_FILES = $(unixdomain_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(unixdomain_PYTHON) $(unixdomain_DATA)
