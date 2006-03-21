common_cflags = -Wall
common_ldflags = -module -avoid-version

flumotiondir = $(libdir)/flumotion/python/flumotion/extern/fdpass

flumotion_LTLIBRARIES = fdpass.la

INCLUDES = $(PYTHON_INCLUDES)

fdpass_la_CFLAGS = $(common_cflags)
fdpass_la_LDFLAGS = $(common_ldflags)
fdpass_la_SOURCES = fdpass.c

