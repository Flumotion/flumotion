dnl as-libtool-tags.m4 0.1.4

dnl autostars m4 macro for selecting libtool "tags" (languages)

dnl Andy Wingo does not claim credit for this macro
dnl backported from libtool 1.6 by Paolo Bonzini
dnl see http://lists.gnu.org/archive/html/libtool/2003-12/msg00007.html

dnl $Id: as-libtool-tags.m4,v 1.2 2005/07/18 14:54:33 wingo Exp $

dnl AS_LIBTOOL_TAGS([tags...])

dnl example
dnl AS_LIBTOOL_TAGS([]) for only C (no fortran, etc)

dnl When AC_LIBTOOL_TAGS is used, I redefine _LT_AC_TAGCONFIG
dnl to be more similar to the libtool 1.6 implementation, which
dnl uses an m4 loop and m4 case instead of a shell loop.  This
dnl way the CXX/GCJ/F77/RC tests are not always expanded.

dnl AS_LIBTOOL_TAGS
dnl ---------------
dnl tags to enable
AC_DEFUN([AS_LIBTOOL_TAGS],
[m4_define([_LT_TAGS],[$1])
m4_define([_LT_AC_TAGCONFIG], [
  if test -f "$ltmain"; then
    if test ! -f "${ofile}"; then
      AC_MSG_WARN([output file `$ofile' does not exist])
    fi

    if test -z "$LTCC"; then
      eval "`$SHELL ${ofile} --config | grep '^LTCC='`"
      if test -z "$LTCC"; then
        AC_MSG_WARN([output file `$ofile' does not look like a libtool script])
      else
        AC_MSG_WARN([using `LTCC=$LTCC', extracted from `$ofile'])
      fi
    fi

    AC_FOREACH([_LT_TAG], _LT_TAGS,
      [m4_case(_LT_TAG,
      [CXX], [
    if test -n "$CXX" && test "X$CXX" != "Xno"; then
      AC_LIBTOOL_LANG_CXX_CONFIG
      available_tags="$available_tags _LT_TAG"
    fi],
      [F77], [
    if test -n "$F77" && test "X$F77" != "Xno"; then
      AC_LIBTOOL_LANG_F77_CONFIG
      available_tags="$available_tags _LT_TAG"
    fi],
      [GCJ], [
    if test -n "$GCJ" && test "X$GCJ" != "Xno"; then
      AC_LIBTOOL_LANG_GCJ_CONFIG
      available_tags="$available_tags _LT_TAG"
    fi],
      [RC], [
    if test -n "$RC" && test "X$RC" != "Xno"; then
      AC_LIBTOOL_LANG_RC_CONFIG
      available_tags="$available_tags _LT_TAG"
    fi],
      [m4_errprintn(m4_location[: error: invalid tag name: ]"_LT_TAG")
      m4_exit(1)])
    ])
  fi

])dnl _LT_AC_TAG_CONFIG
])
