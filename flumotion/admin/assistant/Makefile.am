include $(top_srcdir)/common/python.mk

componentdir = $(libdir)/flumotion/python/flumotion/admin/assistant
component_PYTHON =              \
        __init__.py             \
        configurationwriter.py  \
        interfaces.py           \
        models.py               \
        save.py

TAGS_FILES = $(component_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo
