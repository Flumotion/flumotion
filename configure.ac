AC_INIT(README)

AS_VERSION(flumotion, FLUMOTION, 0, 0, 1, 1)
AC_SUBST(RELEASE, $FLUMOTION_RELEASE)

dnl AM_CONFIG_HEADER(config.h)

AC_SUBST_FILE(AUTHORS)
AUTHORS=$srcdir/AUTHORS

AC_SUBST(PYGTK_REQ, 2.3.96)
AC_SUBST(PYGST_REQ, 0.7.91)
AC_SUBST(GST_REQ, 0.8.5.1)

AM_INIT_AUTOMAKE($PACKAGE, $VERSION)
AC_SUBST(ACLOCAL_AMFLAGS, "-I m4")

AS_AC_EXPAND(DATADIR, $datadir)
AC_MSG_NOTICE(Storing data files in $DATADIR)

AS_AC_EXPAND(SYSCONFDIR, $sysconfdir)
AC_MSG_NOTICE(Storing configuration files in $SYSCONFDIR)

AS_AC_EXPAND(LOCALSTATEDIR, $localstatedir)
AC_MSG_NOTICE(Using localstatedir $LOCALSTATEDIR)

AC_DISABLE_STATIC
AC_PROG_LIBTOOL

dnl check for python
AM_PATH_PYTHON(2.3)
AM_CHECK_PYTHON_HEADERS(,[AC_MSG_ERROR(could not find Python headers)])

dnl check for GStreamer
PKG_CHECK_MODULES(GST, gstreamer-0.8 >= $GST_REQ)

dnl check for pygtk
PKG_CHECK_MODULES(PYGTK, pygtk-2.0 >= $PYGTK_REQ)
PYGTK_DIR="`$PKG_CONFIG --variable=pyexecdir pygtk-2.0`"
AC_SUBST(PYGTK_DIR)

dnl check for gst-python
PKG_CHECK_MODULES(PYGST, gst-python-0.8 >= $PYGST_REQ)
PYGST_DIR="`$PKG_CONFIG --variable=pyexecdir gst-python-0.8`"
AC_SUBST(PYGST_DIR)

dnl check for epydoc
AC_CHECK_PROG(EPYDOC, epydoc, yes, no)
AM_CONDITIONAL(HAVE_EPYDOC, test "x$EPYDOC" = "xyes")

dnl output stuff
AC_OUTPUT(
Makefile
bin/flumotion-manager
bin/flumotion-admin
bin/flumotion-worker
bin/flumotion-tester
bin/runtest
bin/Makefile
data/Makefile
data/glade/Makefile
data/image/Makefile
data/image/wizard/Makefile
flumotion/Makefile
flumotion/admin/Makefile
flumotion/admin/gtk/Makefile
flumotion/common/Makefile
flumotion/component/Makefile
flumotion/component/base/Makefile
flumotion/component/bouncers/Makefile
flumotion/component/encoders/Makefile
flumotion/component/consumers/Makefile
flumotion/component/consumers/disker/Makefile
flumotion/component/consumers/httpstreamer/Makefile
flumotion/component/muxers/Makefile
flumotion/component/overlay/Makefile
flumotion/component/producers/Makefile
flumotion/component/producers/audiotest/Makefile
flumotion/component/producers/bttv/Makefile
flumotion/component/producers/dv/Makefile
flumotion/component/producers/soundcard/Makefile
flumotion/component/producers/videotest/Makefile
flumotion/component/webcam/Makefile
flumotion/configure/Makefile
flumotion/configure/installed.py
flumotion/configure/uninstalled.py
flumotion/manager/Makefile
flumotion/test/Makefile
flumotion/tester/Makefile
flumotion/twisted/Makefile
flumotion/utils/Makefile
flumotion/wizard/Makefile
flumotion/worker/Makefile
m4/Makefile
conf/Makefile
doc/Makefile
doc/reference/Makefile
flumotion.spec
)
