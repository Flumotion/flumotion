include $(top_srcdir)/common/python.mk
                                                                                
flumotiondir = $(libdir)/flumotion/python/flumotion/manager

flumotion_PYTHON =	\
	__init__.py	\
	admin.py	\
	base.py		\
	component.py	\
	main.py		\
	manager.py	\
	worker.py

TAGS_FILES = $(flumotion_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(flumotion_PYTHON)
