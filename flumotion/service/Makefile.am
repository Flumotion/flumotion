include $(top_srcdir)/python.mk
                                                                                
flumotiondir = $(libdir)/flumotion/python/flumotion/service

flumotion_PYTHON = \
	__init__.py 	\
	main.py 	\
	service.py

TAGS_FILES = $(flumotion_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(flumotion_PYTHON)
