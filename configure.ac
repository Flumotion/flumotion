AC_INIT(README)

AS_VERSION(flumotion, FLUMOTION, 0, 0, 0, 1)
AC_SUBST(RELEASE, $FLUMOTION_RELEASE)

dnl AM_CONFIG_HEADER(config.h)

AC_SUBST_FILE(AUTHORS)
AUTHORS=$srcdir/AUTHORS

AC_SUBST(PYGTK_REQ, 2.3.95)
AC_SUBST(PYGST_REQ, 0.7.91)

AM_INIT_AUTOMAKE($PACKAGE, $VERSION)
AC_SUBST(ACLOCAL_AMFLAGS, "-I m4")

AS_AC_EXPAND(DATADIR, $datadir)
AC_MSG_NOTICE(Storing data files in $DATADIR)

dnl AS_AC_EXPAND(SYSCONFDIR, $sysconfdir)
dnl AC_MSG_NOTICE(Storing configuration files in $SYSCONFDIR)

dnl AS_AC_EXPAND(LOCALSTATEDIR, $localstatedir)
dnl AC_MSG_NOTICE(Using localstatedir $LOCALSTATEDIR)

AC_DISABLE_STATIC
AC_PROG_LIBTOOL

dnl check for python
AM_PATH_PYTHON(2.3)
AM_CHECK_PYTHON_HEADERS(,[AC_MSG_ERROR(could not find Python headers)])

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
bin/flumotion
bin/flumotion-admin
bin/Makefile
data/Makefile
data/glade/Makefile
data/image/Makefile
flumotion/Makefile
flumotion/admin/Makefile
flumotion/admin/gtk/Makefile
flumotion/common/Makefile
flumotion/component/Makefile
flumotion/component/base/Makefile
flumotion/component/bttv/Makefile
flumotion/component/dv/Makefile
flumotion/component/file/Makefile
flumotion/component/http/Makefile
flumotion/component/multipartjpeg/Makefile
flumotion/component/overlay/Makefile
flumotion/component/passwd/Makefile
flumotion/component/videotest/Makefile
flumotion/config/Makefile
flumotion/config/installed.py
flumotion/config/uninstalled.py
flumotion/manager/Makefile
flumotion/twisted/Makefile
flumotion/utils/Makefile
m4/Makefile
conf/Makefile
doc/Makefile
doc/reference/Makefile
testsuite/Makefile
testsuite/tests/Makefile
testsuite/common.py
flumotion.spec
)
