include $(top_srcdir)/common/python.mk
                                                                                
flumotiondir = $(libdir)/flumotion/python/flumotion/twisted

flumotion_PYTHON = \
	__init__.py \
	checkers.py \
	credentials.py \
	defer.py \
	fdserver.py \
	flavors.py \
	http.py \
	integration.py \
	pb.py \
	portal.py \
	reflect.py \
	rtsp.py

TAGS_FILES = $(flumotion_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(flumotion_PYTHON)
