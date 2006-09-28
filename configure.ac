AC_INIT(README)

AS_VERSION(flumotion, FLUMOTION, 0, 3, 1, 0)
AC_SUBST(RELEASE, $FLUMOTION_RELEASE)

AC_SUBST_FILE(AUTHORS)
AUTHORS=$srcdir/AUTHORS

AC_SUBST(PYGTK_010_REQ, 2.6.3)
AC_SUBST(PYGST_010_REQ, 0.10.0)
AC_SUBST(GST_010_REQ, 0.10.0.1)

GST_010_SUPPORTED=true

AM_INIT_AUTOMAKE($PACKAGE, $VERSION)

dnl Add parameters for aclocal
AC_SUBST(ACLOCAL_AMFLAGS, "-I m4 -I common")

dnl set up gettext
dnl the version check needs to stay here because autopoint greps for it
AM_GNU_GETTEXT_VERSION([0.11.5])
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

AS_AC_EXPAND(SBINDIR, $sbindir)
AC_MSG_NOTICE(Using sbindir $SBINDIR)

AC_DISABLE_STATIC
AS_LIBTOOL_TAGS([])
AC_PROG_LIBTOOL

dnl check for python
AS_PATH_PYTHON(2.3)

AM_CHECK_PYTHON_HEADERS(HAVE_PYTHON_H=yes, [
  AC_MSG_ERROR([You need to install the Python development packages.])
])

dnl check for GStreamer
PKG_CHECK_MODULES(GST_010, gstreamer-0.10 >= $GST_010_REQ,
    [GST_010_SUPPORTED=yes], [AC_MSG_RESULT([$GST_010_PKG_ERRORS]); GST_010_SUPPORTED=no])

if test $GST_010_SUPPORTED = "no"; then
  AC_MSG_ERROR([No GStreamer development packages found.
Please install GStreamer development packages for version 0.10.
Also, check your PKG_CONFIG_PATH.])
fi  

export PYTHONPATH=$PYGTK_DIR:$PYTHONPATH
PKG_CHECK_MODULES(PYGTK, pygtk-2.0 >= $PYGTK_010_REQ)
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

if test $GST_010_SUPPORTED = "no"; then
  AC_MSG_ERROR([No appropriate version of PyGTK installed. Correct the above
errors and try again.])
fi

dnl checks for gst-python
if test $GST_010_SUPPORTED = "yes"; then
  PKG_CHECK_MODULES(PYGST_010, gst-python-0.10 >= $PYGST_010_REQ,
      [PYGST_010_DIR="`$PKG_CONFIG --variable=pyexecdir gst-python-0.10`"
       AC_SUBST(PYGST_010_DIR)
       AC_MSG_NOTICE(Using gstreamer-python 0.10 installed in $PYGST_010_DIR)],
      [AC_MSG_RESULT([$PYGST_010_PKG_ERRORS])
       GST_010_SUPPORTED=no])

  if test $GST_010_SUPPORTED = "yes"; then
    saved_PYTHONPATH=$PYTHONPATH
    export PYTHONPATH=$PYGST_010_DIR:$PYTHONPATH
    AS_PYTHON_IMPORT([gst],,
                     [AC_MSG_NOTICE([Unable to import gst-python 0.10 -- check your PYTHONPATH?])
                      GST_010_SUPPORTED=no],
                     [import pygst; pygst.require('0.10')],
                     [assert gst.pygst_version[[1]] == 10 or (gst.pygst_version[[1]] == 9 and gst.pygst_version[[2]] >= 7)])

  fi
fi

if test $GST_010_SUPPORTED = "no"; then
  AC_MSG_ERROR([No suitable gstreamer-python versions found. Correct the above
errors and try again.])
fi  

AC_SUBST(GST_010_SUPPORTED)

FLU_PKG_CONFIG_REQUIRES="gstreamer-0.10 >= $GST_010_REQ"
AC_SUBST(FLU_PKG_CONFIG_REQUIRES)

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
minver = '2.0.1'
if twisted.copyright.version < minver:
    sys.exit(1)
sys.exit(0)
"
  if $PYTHON -c "$prog" 1>&AC_FD_CC 2>&AC_FD_CC
  then
    AC_MSG_RESULT(found)
  else
    AC_MSG_RESULT(too old)
    AC_MSG_ERROR([You need at least version 2.0.1 of Twisted])
  fi
  ]
  ,
  AC_MSG_ERROR([You need at least version 2.0.1 of Twisted])
)

TWISTED_MODULE([twisted.names])
TWISTED_MODULE([twisted.web])

AC_CONFIG_FILES([env], [chmod +x env])
AC_CONFIG_FILES([bin/flumotion], [chmod +x bin/flumotion])
AC_CONFIG_FILES([bin/flumotion-admin], [chmod +x bin/flumotion-admin])
AC_CONFIG_FILES([bin/flumotion-admin-text], [chmod +x bin/flumotion-admin-text])
AC_CONFIG_FILES([bin/flumotion-command], [chmod +x bin/flumotion-command])
AC_CONFIG_FILES([bin/flumotion-inspect], [chmod +x bin/flumotion-inspect])
AC_CONFIG_FILES([bin/flumotion-job], [chmod +x bin/flumotion-job])
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
flumotion/admin/command/Makefile
flumotion/admin/gtk/Makefile
flumotion/admin/text/Makefile
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
flumotion/component/converters/pipeline/Makefile
flumotion/component/converters/overlay/Makefile
flumotion/component/misc/Makefile
flumotion/component/misc/gdptestsrc/Makefile
flumotion/component/misc/httpfile/Makefile
flumotion/component/misc/porter/Makefile
flumotion/component/misc/repeater/Makefile
flumotion/component/muxers/Makefile
flumotion/component/plugs/Makefile
flumotion/component/producers/Makefile
flumotion/component/producers/audiotest/Makefile
flumotion/component/producers/bttv/Makefile
flumotion/component/producers/firewire/Makefile
flumotion/component/producers/pipeline/Makefile
flumotion/component/producers/soundcard/Makefile
flumotion/component/producers/videotest/Makefile
flumotion/component/producers/webcam/Makefile
flumotion/component/producers/looper/Makefile
flumotion/configure/Makefile
flumotion/configure/installed.py
flumotion/configure/uninstalled.py
flumotion/extern/Makefile
flumotion/extern/fdpass/Makefile
flumotion/extern/pytrayicon/Makefile
flumotion/job/Makefile
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
tests/Makefile
tests/integration/Makefile
flumotion.spec
po/Makefile.in
)

echo
echo "configure: *** Flumotion has been configured with support for the"
echo "               following versions of GStreamer:"
echo
echo "    GStreamer 0.10: $GST_010_SUPPORTED"
echo
echo "If either version is disabled, check the configure output above to"
echo "determine the cause of the problem, and re-run the configure"
echo "script after installing the necessary dependencies."
echo
