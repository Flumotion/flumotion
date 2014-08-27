include $(top_srcdir)/common/python.mk

plugutilsdir = $(libdir)/flumotion/python/flumotion/component/plugs/utils

plugutils_PYTHON =      \
        __init__.py     \
        user_agent_parser.py

TAGS_FILES = $(plugutils_PYTHON)
ETAGS_ARGS = --lang=python $(plugutils_PYTHON)

clean-local:
        rm -rf *.pyc *.pyo

EXTRA_DIST = $(plugutils_PYTHON)
