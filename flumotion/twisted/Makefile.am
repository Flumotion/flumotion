include $(top_srcdir)/python.mk
                                                                                
flumotiondir = $(libdir)/flumotion/python/flumotion/twisted

flumotion_PYTHON = \
	__init__.py \
	checkers.py \
	compat.py \
	credentials.py \
	defer.py \
	flavors.py \
	gstreactor.py \
	gtk2reactor.py \
	pb.py \
	portal.py \
	reflect.py

TAGS_FILES = $(flumotion_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(flumotion_PYTHON)
