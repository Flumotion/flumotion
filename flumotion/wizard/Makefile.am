include $(top_srcdir)/common/python.mk

flumotiondir = $(libdir)/flumotion/python/flumotion/wizard

flumotion_PYTHON =              \
        __init__.py             \
        basesteps.py            \
        consumptionsteps.py     \
        conversionsteps.py      \
        diskersteps.py          \
        httpstreamersteps.py    \
        ondemandstep.py         \
        overlaystep.py          \
        productionsteps.py      \
        scenarios.py            \
        shout2steps.py          \
        worker.py               \
        workerstep.py

TAGS_FILES = $(flumotion_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(flumotion_PYTHON)
