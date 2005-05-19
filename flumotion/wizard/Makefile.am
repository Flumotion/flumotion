include $(top_srcdir)/common/python.mk
                                                                                
flumotiondir = $(libdir)/flumotion/python/flumotion/wizard

flumotion_PYTHON = \
	__init__.py \
	enums.py \
	save.py \
	sidebar.py \
	step.py \
	steps.py \
	types.py \
	wizard.py

TAGS_FILES = $(flumotion_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(flumotion_PYTHON)
