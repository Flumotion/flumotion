include $(top_srcdir)/common/python.mk

cachedhttpdir = $(libdir)/flumotion/python/flumotion/component/misc/httpserver/httpcached

cachedhttp_PYTHON = \
	__init__.py \
	common.py \
	file_provider.py \
	file_reader.py \
	http_client.py \
	http_utils.py \
	request_manager.py \
	resource_manager.py \
	server_selection.py \
	strategy_base.py \
	strategy_basic.py

cachedhttp_DATA = \
	httpcached.xml

TAGS_FILES = $(cachedhttp_PYTHON)

clean-local:
	rm -rf *.pyc *.pyo

EXTRA_DIST = $(cachedhttp_PYTHON) $(cachedhttp_DATA)
