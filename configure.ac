AC_INIT(README)

AS_VERSION(flumotion, FLUMOTION, 0, 1, 4, 0)
AC_SUBST(RELEASE, $FLUMOTION_RELEASE)

AC_SUBST_FILE(AUTHORS)
AUTHORS=$srcdir/AUTHORS

AC_SUBST(PYGTK_REQ, 2.4.0)
AC_SUBST(PYGST_REQ, 0.7.94)
AC_SUBST(GST_REQ, 0.8.7)

AM_INIT_AUTOMAKE($PACKAGE, $VERSION)
AC_SUBST(ACLOCAL_AMFLAGS, "-I m4")

AS_AC_EXPAND(LIBDIR, $libdir)
AC_MSG_NOTICE(Storing library files in $LIBDIR)

AS_AC_EXPAND(DATADIR, $datadir)
AC_MSG_NOTICE(Storing data files in $DATADIR)

AS_AC_EXPAND(SYSCONFDIR, $sysconfdir)
AC_MSG_NOTICE(Storing configuration files in $SYSCONFDIR)

AS_AC_EXPAND(LOCALSTATEDIR, $localstatedir)
AC_MSG_NOTICE(Using localstatedir $LOCALSTATEDIR)

AC_DISABLE_STATIC
AC_PROG_LIBTOOL

dnl check for python
AS_PATH_PYTHON(2.3)
dnl useful when we compile our own python modules
dnl AM_CHECK_PYTHON_HEADERS(,[AC_MSG_ERROR(could not find Python headers)])

dnl check for GStreamer
PKG_CHECK_MODULES(GST, gstreamer-0.8 >= $GST_REQ)

dnl check for pygtk
PKG_CHECK_MODULES(PYGTK, pygtk-2.0 >= $PYGTK_REQ)
PYGTK_DIR="`$PKG_CONFIG --variable=pyexecdir pygtk-2.0`"
AC_SUBST(PYGTK_DIR)
AC_MSG_NOTICE(Using pygtk installed in $PYGTK_DIR)

export PYTHONPATH=$PYGTK_DIR:$PYTHONPATH

dnl check for libglade
AC_MSG_CHECKING(for gtk.glade)
prog="
import sys
try:
  import gtk.glade
except RuntimeError:
  sys.exit(0)
except ImportError:
  sys.exit(1)
sys.exit(0)
"

if $PYTHON -c "$prog" 1>&AC_FD_CC 2>&AC_FD_CC
then
  AC_MSG_RESULT(found)
else
  AC_MSG_RESULT(not found)
  AC_MSG_ERROR([You need to have python libglade bindings installed])
fi

dnl checks for gst-python
PKG_CHECK_MODULES(PYGST, gst-python-0.8 >= $PYGST_REQ)
PYGST_DIR="`$PKG_CONFIG --variable=pyexecdir gst-python-0.8`"
AC_SUBST(PYGST_DIR)
AC_MSG_NOTICE(Using gstreamer-python installed in $PYGST_DIR)

export PYTHONPATH=$PYGST_DIR:$PYTHONPATH
AS_PYTHON_IMPORT([gst],,
                 AC_MSG_ERROR([Maybe you forgot to set your PYTHONPATH?]))

AS_PYTHON_IMPORT([gst, gst.interfaces],,
                 AC_MSG_ERROR([You need to recompile gst-python with gst.interfaces support]))

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

dnl output stuff
AC_OUTPUT(
Makefile
bin/flumotion
bin/flumotion-admin
bin/flumotion-manager
bin/flumotion-tester
bin/flumotion-worker
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
flumotion/component/effects/Makefile
flumotion/component/effects/colorbalance/Makefile
flumotion/component/effects/volume/Makefile
flumotion/component/encoders/Makefile
flumotion/component/consumers/Makefile
flumotion/component/consumers/disker/Makefile
flumotion/component/consumers/httpstreamer/Makefile
flumotion/component/converters/Makefile
flumotion/component/converters/overlay/Makefile
flumotion/component/muxers/Makefile
flumotion/component/producers/Makefile
flumotion/component/producers/audiotest/Makefile
flumotion/component/producers/bttv/Makefile
flumotion/component/producers/firewire/Makefile
flumotion/component/producers/soundcard/Makefile
flumotion/component/producers/videotest/Makefile
flumotion/component/producers/webcam/Makefile
flumotion/configure/Makefile
flumotion/configure/installed.py
flumotion/configure/uninstalled.py
flumotion/manager/Makefile
flumotion/service/Makefile
flumotion/test/Makefile
flumotion/tester/Makefile
flumotion/twisted/Makefile
flumotion/ui/Makefile
flumotion/utils/Makefile
flumotion/wizard/Makefile
flumotion/worker/Makefile
m4/Makefile
conf/Makefile
doc/Makefile
doc/reference/Makefile
pkgconfig/Makefile
pkgconfig/flumotion.pc
pkgconfig/flumotion-uninstalled.pc
flumotion.spec
)
