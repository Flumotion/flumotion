AC_INIT(README)

AS_VERSION(flumotion, FLUMOTION, 0, 0, 0, 1)
AC_SUBST(RELEASE, $FLUMOTION_RELEASE)

AC_SUBST_FILE(AUTHORS)
AUTHORS=$srcdir/AUTHORS

AC_SUBST(PYGTK_REQ, 2.0.0)
AC_SUBST(PYGST_REQ, 0.7.91)

AM_INIT_AUTOMAKE($PACKAGE, $VERSION)
AC_SUBST(ACLOCAL_AMFLAGS, "-I m4")

dnl AS_AC_EXPAND(SYSCONFDIR, $sysconfdir)
dnl AC_MSG_NOTICE(Storing configuration files in $SYSCONFDIR)

dnl AS_AC_EXPAND(LOCALSTATEDIR, $localstatedir)
dnl AC_MSG_NOTICE(Using localstatedir $LOCALSTATEDIR)

AC_DISABLE_STATIC
AC_PROG_LIBTOOL

dnl check for python
AM_PATH_PYTHON(2.2)
AM_CHECK_PYTHON_HEADERS(,[AC_MSG_ERROR(could not find Python headers)])

dnl check for pygtk
PKG_CHECK_MODULES(PYGTK, pygtk-2.0 >= $PYGTK_REQ)

PYGTK_DIR="`$PKG_CONFIG --variable=pyexecdir pygtk-2.0`"
AC_SUBST(PYGTK_DIR)

dnl check for gst-python
PKG_CHECK_MODULES(PYGST, gst-python-0.8 >= $PYGST_REQ)

dnl check for epydoc
AC_CHECK_PROG(EPYDOC, epydoc, yes, no)
AM_CONDITIONAL(HAVE_EPYDOC, test "x$EPYDOC" = "xyes")

dnl output stuff
AC_OUTPUT(
Makefile
bin/flumotion
bin/video-server-admin
bin/Makefile
data/Makefile
data/ui/Makefile
flumotion/Makefile
flumotion/gui/Makefile
flumotion/server/Makefile
flumotion/twisted/Makefile
flumotion/utils/Makefile
m4/Makefile
docs/Makefile
flumotion.spec
)
