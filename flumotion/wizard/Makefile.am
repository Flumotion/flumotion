include $(top_srcdir)/common/python.mk

flumotiondir = $(libdir)/flumotion/python/flumotion/wizard

flumotion_PYTHON = 		\
	__init__.py 		\
	basesteps.py 		\
	configurationwizard.py 	\
	consumptionsteps.py 	\
	conversionsteps.py 	\
	enums.py 		\
	models.py 		\
	overlaystep.py 		\
	productionsteps.py 	\
	save.py 		\
	worker.py 		\
	workerstep.py

TAGS_FILES = $(flumotion_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(flumotion_PYTHON)
