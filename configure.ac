AC_INIT(README)

AS_VERSION(flumotion, FLUMOTION, 0, 0, 0, 1)
AC_SUBST(RELEASE, $FLUMOTION_RELEASE)

AC_SUBST_FILE(AUTHORS)
AUTHORS=$srcdir/AUTHORS

AM_INIT_AUTOMAKE($PACKAGE, $VERSION)
AC_SUBST(ACLOCAL_AMFLAGS, "-I m4")

dnl AS_AC_EXPAND(SYSCONFDIR, $sysconfdir)
dnl AC_MSG_NOTICE(Storing configuration files in $SYSCONFDIR)

dnl AS_AC_EXPAND(LOCALSTATEDIR, $localstatedir)
dnl AC_MSG_NOTICE(Using localstatedir $LOCALSTATEDIR)

dnl check for python
AM_PATH_PYTHON
#AS_PATH_PYTHON(2.2)
if test "x$PYTHON" == "x"; then
  AC_MSG_ERROR(No suitable python version found)
fi

dnl check for epydoc
AC_CHECK_PROG(EPYDOC, epydoc, yes, no)
AM_CONDITIONAL(HAVE_EPYDOC, test "x$EPYDOC" = "xyes")

dnl output stuff
AC_OUTPUT(
Makefile
flumotion/Makefile
m4/Makefile
docs/Makefile
flumotion.spec
)
