AC_INIT(README)

AS_VERSION(flumotion, FLUMOTION, 0, 1, 9, 1)
AC_SUBST(RELEASE, $FLUMOTION_RELEASE)

AC_SUBST_FILE(AUTHORS)
AUTHORS=$srcdir/AUTHORS

AC_SUBST(PYGTK_BASE_REQ, 2.4.0)

AC_SUBST(PYGTK_08_REQ, 2.4.0)
AC_SUBST(PYGST_08_REQ, 0.8.0)
AC_SUBST(GST_08_REQ, 0.8.7)

AC_SUBST(PYGTK_09_REQ, 2.6.3)
AC_SUBST(PYGST_09_REQ, 0.9.0)
AC_SUBST(GST_09_REQ, 0.9.2)

GST_08_SUPPORTED=true
GST_09_SUPPORTED=true

AM_INIT_AUTOMAKE($PACKAGE, $VERSION)
AC_SUBST(ACLOCAL_AMFLAGS, "-I common")

dnl gettext
AM_GNU_GETTEXT_VERSION(0.11.5)
AM_GNU_GETTEXT([external])

GETTEXT_PACKAGE=$PACKAGE
AC_SUBST(GETTEXT_PACKAGE)

AS_AC_EXPAND(LIBDIR, $libdir)
AC_MSG_NOTICE(Storing library files in $LIBDIR)

AS_AC_EXPAND(DATADIR, $datadir)
AC_MSG_NOTICE(Storing data files in $DATADIR)

AS_AC_EXPAND(SYSCONFDIR, $sysconfdir)
AC_MSG_NOTICE(Storing configuration files in $SYSCONFDIR)

AS_AC_EXPAND(LOCALSTATEDIR, $localstatedir)
AC_MSG_NOTICE(Using localstatedir $LOCALSTATEDIR)

AC_DISABLE_STATIC
AS_LIBTOOL_TAGS([])
AC_PROG_LIBTOOL

dnl check for python
AS_PATH_PYTHON(2.3)

AM_CHECK_PYTHON_HEADERS(HAVE_PYTHON_H=yes, HAVE_PYTHON_H=no)

dnl check for GStreamer
PKG_CHECK_MODULES(GST_08, gstreamer-0.8 >= $GST_08_REQ,
    [GST_08_SUPPORTED=yes], [AC_MSG_RESULT([$GST_08_PKG_ERRORS]); GST_08_SUPPORTED=no])
PKG_CHECK_MODULES(GST_09, gstreamer-0.9 >= $GST_09_REQ,
    [GST_09_SUPPORTED=yes], [AC_MSG_RESULT([$GST_09_PKG_ERRORS]); GST_09_SUPPORTED=no])

if test $GST_08_SUPPORTED = "no" -a $GST_09_SUPPORTED = "no"; then
  AC_MSG_ERROR([No GStreamer development packages found.
Please install GStreamer development packages for version 0.8 or 0.9 (or both).
Also, check your PKG_CONFIG_PATH.])
fi  

export PYTHONPATH=$PYGTK_DIR:$PYTHONPATH
PKG_CHECK_MODULES(PYGTK, pygtk-2.0 >= $PYGTK_08_REQ)
PYGTK_DIR="`$PKG_CONFIG --variable=pyexecdir pygtk-2.0`"
AC_SUBST(PYGTK_DIR)
AC_MSG_NOTICE(Using pygtk installed in $PYGTK_DIR)
PYGTK_VERSION="`$PKG_CONFIG --modversion pygtk-2.0`"

if test "x$PYGTK_VERSION" = "x2.5.2"
then
  AC_MSG_ERROR([PyGTK 2.5.2 contains known bugs, please install other version])
fi

if test "x$DISPLAY" != "x"; then
  AS_PYTHON_IMPORT([gtk.glade],,
                   AC_MSG_ERROR([You need to have python libglade bindings installed]))
else
  AC_MSG_NOTICE([Not trying to import gtk.glade because DISPLAY is unset])
fi

if test $GST_09_SUPPORTED = "yes"; then
  AC_MSG_CHECKING([if found PyGTK version is new enough to support GStreamer 0.9])
  if test "$PYGTK_VERSION" \< $PYGTK_09_REQ; then
    AC_MSG_RESULT([no, $PYGTK_VERSION < $PYGTK_09_REQ])
    GST_09_SUPPORTED=no
  else
    AC_MSG_RESULT([yes, $PYGTK_VERSION >= $PYGTK_09_REQ])
  fi
fi

if test $GST_08_SUPPORTED = "no" -a $GST_09_SUPPORTED = "no"; then
  AC_MSG_ERROR([No appropriate version of PyGTK installed. Correct the above
errors and try again.])
fi

dnl checks for gst-python
if test $GST_08_SUPPORTED = "yes"; then
  PKG_CHECK_MODULES(PYGST_08, gst-python-0.8 >= $PYGST_08_REQ,
      [PYGST_08_DIR="`$PKG_CONFIG --variable=pyexecdir gst-python-0.8`"
       AC_SUBST(PYGST_08_DIR)
       AC_MSG_NOTICE(Using gstreamer-python 0.8 installed in $PYGST_08_DIR)],
      [AC_MSG_RESULT([$PYGST_08_PKG_ERRORS])
       GST_08_SUPPORTED=no])

  if test $GST_08_SUPPORTED = "yes"; then
    saved_PYTHONPATH=$PYTHONPATH
    export PYTHONPATH=$PYGST_08_DIR:$PYTHONPATH
    AS_PYTHON_IMPORT([gst],,
                     [AC_MSG_NOTICE([Unable to import gst-python 0.8 -- check your PYTHONPATH?])
                      GST_08_SUPPORTED=no],,
                     [assert gst.pygst_version[[1]] == 8])

    if test $GST_08_SUPPORTED = "yes"; then
      AS_PYTHON_IMPORT([gst, gst.interfaces],,
                       [AC_MSG_NOTICE([You need to recompile gst-python 0.8 with gst.interfaces support])
                        GST_08_SUPPORTED=no])
      export PYTHONPATH=$saved_PYTHONPATH
    fi
  fi
fi

if test $GST_09_SUPPORTED = "yes"; then
  PKG_CHECK_MODULES(PYGST_09, gst-python-0.9 >= $PYGST_09_REQ,
      [PYGST_09_DIR="`$PKG_CONFIG --variable=pyexecdir gst-python-0.9`"
       AC_SUBST(PYGST_09_DIR)
       AC_MSG_NOTICE(Using gstreamer-python 0.9 installed in $PYGST_09_DIR)],
      [AC_MSG_RESULT([$PYGST_09_PKG_ERRORS])
       GST_09_SUPPORTED=no])

  if test $GST_09_SUPPORTED = "yes"; then
    saved_PYTHONPATH=$PYTHONPATH
    export PYTHONPATH=$PYGST_09_DIR:$PYTHONPATH
    AS_PYTHON_IMPORT([gst],,
                     [AC_MSG_NOTICE([Unable to import gst-python 0.9 -- check your PYTHONPATH?])
                      GST_09_SUPPORTED=no],
                     [import pygst; pygst.require('0.9')],
                     [assert gst.pygst_version[[1]] == 9])

    if test $GST_08_SUPPORTED = "yes"; then
      AS_PYTHON_IMPORT([gst, gst.interfaces],,
                       [AC_MSG_NOTICE([You need to recompile gst-python 0.9 with gst.interfaces support])
                        GST_09_SUPPORTED=no],
                       [import pygst; pygst.require('0.9')])
      export PYTHONPATH=$saved_PYTHONPATH
    fi
  fi
fi

if test $GST_08_SUPPORTED = "no" -a $GST_09_SUPPORTED = "no"; then
  AC_MSG_ERROR([No suitably gstreamer-python versions found. Correct the above
errors and try again.])
fi  

AC_SUBST(GST_08_SUPPORTED)
AC_SUBST(GST_09_SUPPORTED)

dnl check stuff we can generate the tray icon with
AC_MSG_CHECKING(for pygtk codegen)
PYGTK_CODEGEN="$PYTHON `$PKG_CONFIG --variable=codegendir pygtk-2.0`/codegen.py"
dnl PYGTK_CODEGEN="$PYTHON \$(top_srcdir)/codegen/codegen.py"
AC_SUBST(PYGTK_CODEGEN)
AC_MSG_RESULT($PYGTK_CODEGEN)

AC_MSG_CHECKING(for pygtk defsdir)
PYGTK_DEFSDIR=`$PKG_CONFIG --variable=defsdir pygtk-2.0`
AC_SUBST(PYGTK_DEFSDIR)
AC_MSG_RESULT($PYGTK_DEFSDIR)

PKG_CHECK_MODULES(GTK, gtk+-2.0, HAVE_GTK=yes, HAVE_GTK=no)

# decide on tray icon
BUILD_TRAYICON=yes
if test "x$HAVE_PYTHON_H" = "xno"
then
  AC_MSG_NOTICE([Python headers missing, not building tray icon])
  BUILD_TRAYICON=no
fi
if test "x$HAVE_GTK" = "xno"
then
  AC_MSG_NOTICE([GTK+ 2 development files missing, not building tray icon])
  BUILD_TRAYICON=no
fi

if test "x$BUILD_TRAYICON" = "xyes"
then
  AC_MSG_NOTICE([Building tray icon])
fi

AM_CONDITIONAL(BUILD_TRAYICON, test "x$BUILD_TRAYICON" = "xyes")

dnl check for epydoc
AC_CHECK_PROG(EPYDOC, epydoc, yes, no)
AM_CONDITIONAL(HAVE_EPYDOC, test "x$EPYDOC" = "xyes")

dnl check for pychecker
AC_CHECK_PROG(PYCHECKER, pychecker, yes, no)
AM_CONDITIONAL(HAVE_PYCHECKER, test "x$PYCHECKER" = "xyes")

dnl check for Twisted
AS_PYTHON_IMPORT(twisted,
  [
  AC_MSG_CHECKING(for Twisted >= 1.3.0)
  prog="
import sys
import twisted.copyright
minver = '1.3.0'
if twisted.copyright.version < minver:
    sys.exit(1)
sys.exit(0)
"
  if $PYTHON -c "$prog" 1>&AC_FD_CC 2>&AC_FD_CC
  then
    AC_MSG_RESULT(found)
  else
    AC_MSG_RESULT(too old)
    AC_MSG_ERROR([You need at least version 1.3.0 of Twisted])
  fi
  ]
  ,
  AC_MSG_ERROR([You need at least version 1.3.0 of Twisted])
)

AC_CONFIG_FILES([env], [chmod +x env])
AC_CONFIG_FILES([bin/flumotion], [chmod +x bin/flumotion])
AC_CONFIG_FILES([bin/flumotion-admin], [chmod +x bin/flumotion-admin])
AC_CONFIG_FILES([bin/flumotion-inspect], [chmod +x bin/flumotion-inspect])
AC_CONFIG_FILES([bin/flumotion-launch], [chmod +x bin/flumotion-launch])
AC_CONFIG_FILES([bin/flumotion-manager], [chmod +x bin/flumotion-manager])
AC_CONFIG_FILES([bin/flumotion-tester], [chmod +x bin/flumotion-tester])
AC_CONFIG_FILES([bin/flumotion-worker], [chmod +x bin/flumotion-worker])
AC_CONFIG_FILES([bin/runtest], [chmod +x bin/runtest])

dnl output stuff
AC_OUTPUT(
Makefile
bin/Makefile
common/Makefile
data/Makefile
data/glade/Makefile
data/image/Makefile
data/image/16x16/Makefile
data/image/24x24/Makefile
data/image/wizard/Makefile
data/flumotion-admin.desktop
flumotion/Makefile
flumotion/admin/Makefile
flumotion/admin/gtk/Makefile
flumotion/common/Makefile
flumotion/common/boot.py
flumotion/component/Makefile
flumotion/component/base/Makefile
flumotion/component/bouncers/Makefile
flumotion/component/effects/Makefile
flumotion/component/effects/colorbalance/Makefile
flumotion/component/effects/volume/Makefile
flumotion/component/encoders/Makefile
flumotion/component/consumers/Makefile
flumotion/component/consumers/disker/Makefile
flumotion/component/consumers/httpstreamer/Makefile
flumotion/component/consumers/preview/Makefile
flumotion/component/converters/Makefile
flumotion/component/converters/overlay/Makefile
flumotion/component/muxers/Makefile
flumotion/component/producers/Makefile
flumotion/component/producers/audiotest/Makefile
flumotion/component/producers/bttv/Makefile
flumotion/component/producers/firewire/Makefile
flumotion/component/producers/jukebox/Makefile
flumotion/component/producers/soundcard/Makefile
flumotion/component/producers/videotest/Makefile
flumotion/component/producers/webcam/Makefile
flumotion/configure/Makefile
flumotion/configure/installed.py
flumotion/configure/uninstalled.py
flumotion/extern/Makefile
flumotion/extern/pytrayicon/Makefile
flumotion/launch/Makefile
flumotion/manager/Makefile
flumotion/project/Makefile
flumotion/service/Makefile
flumotion/test/Makefile
flumotion/tester/Makefile
flumotion/twisted/Makefile
flumotion/ui/Makefile
flumotion/wizard/Makefile
flumotion/worker/Makefile
flumotion/worker/checks/Makefile
conf/Makefile
doc/Makefile
doc/reference/Makefile
doc/man/Makefile
pkgconfig/Makefile
pkgconfig/flumotion.pc
pkgconfig/flumotion-uninstalled.pc
flumotion.spec
po/Makefile.in
)

echo
echo "configure: *** Flumotion has been configured with support for the"
echo "               following versions of GStreamer:"
echo
echo "    GStreamer 0.8: $GST_08_SUPPORTED"
echo "    GStreamer 0.9: $GST_09_SUPPORTED"
echo
echo "If either version is disabled, check the configure output above to"
echo "determine the cause of the problem, and re-run the configure"
echo "script after installing the necessary dependencies."
echo
