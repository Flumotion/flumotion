# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007 Fluendo, S.L. (www.fluendo.com).
# All rights reserved.

# This file may be distributed and/or modified under the terms of
# the GNU General Public License version 2 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.GPL" in the source distribution for more information.

# Licensees having purchased or holding a valid Flumotion Advanced
# Streaming Server license may use this file in accordance with the
# Flumotion Advanced Streaming Server Commercial License Agreement.
# See "LICENSE.Flumotion" in the source distribution for more information.

# Headers in this file shall remain intact.

"""boostrapping functions for flumotion"""

import os
import sys

from flumotion.common.log import safeprintf

__version__ = "$Rev$"
# Keep in sync with configure.ac
PYGTK_REQ = (2, 10, 0)
KIWI_REQ = (1, 9, 13)
GST_REQ = {'0.10': {'gstreamer': (0, 10, 10),
                    'gst-python': (0, 10, 4)}}
USE_GOPTION_PARSER = False
USE_GTK = False
USE_GST = True


def init_gobject():
    """
    Initialize pygobject. A missing or too-old pygobject will cause a
    SystemExit exception to be raised.
    """
    try:
        import pygtk
        pygtk.require('2.0')

        import gobject
    except ImportError:
        raise SystemExit('ERROR: PyGTK could not be found')

    if gobject.pygtk_version < PYGTK_REQ:
        raise SystemExit('ERROR: PyGTK %s or higher is required'
                         % '.'.join(map(str, PYGTK_REQ)))

    gobject.threads_init()


def _init_gst_version(gst_majorminor):

    def tup2version(tup):
        return '.'.join(map(str, tup))

    if gst_majorminor not in GST_REQ:
        raise SystemExit('ERROR: Invalid FLU_GST_VERSION: %r (expected '
                         'one of %r)' % (gst_majorminor, GST_REQ.keys()))

    pygst_req = GST_REQ[gst_majorminor]['gst-python']
    gst_req = GST_REQ[gst_majorminor]['gstreamer']

    try:
        import pygst
        pygst.require(gst_majorminor)
        import gst
    except ImportError:
        return False
    except AssertionError:
        return False

    try:
        gst_version = gst.get_gst_version()
        pygst_version = gst.get_pygst_version()
    except AttributeError:
        # get_foo_version() added in 0.10.4, fall back
        gst_version = gst.gst_version
        pygst_version = gst.pygst_version

    if gst_req[:2] != gst_version[:2]:
        raise SystemExit(
            'ERROR: Expected GStreamer %s, but got incompatible %s'
            % (gst_majorminor, tup2version(gst_version[:2])))

    if gst_version < gst_req:
        raise SystemExit(
            'ERROR: GStreamer %s too old; install %s or newer'
            % (tup2version(gst_version), tup2version(gst_req)))

    if pygst_version < pygst_req:
        raise SystemExit(
            'ERROR: gst-python %s too old; install %s or newer'
            % (tup2version(pygst_version), tup2version(pygst_req)))

    return True


def init_gst():
    """
    Initialize pygst. A missing or too-old pygst will cause a
    SystemExit exception to be raised.
    """
    assert 'gobject' in sys.modules, "Run init_gobject() first"

    gst_majorminor = os.getenv('FLU_GST_VERSION')

    if gst_majorminor:
        if not _init_gst_version(gst_majorminor):
            raise SystemExit('ERROR: requested GStreamer version %s '
                             'not available' % gst_majorminor)
    else:
        majorminors = GST_REQ.keys()
        majorminors.sort()
        while majorminors:
            majorminor = majorminors.pop()
            if _init_gst_version(majorminor):
                gst_majorminor = majorminor
                break
        if not gst_majorminor:
            raise SystemExit('ERROR: no GStreamer available '
                             '(looking for versions %r)' % (GST_REQ.keys(), ))

    return gst_majorminor


def init_kiwi():
    import gobject

    try:
        from kiwi.__version__ import version as kiwi_version
    except ImportError:
        return False

    if kiwi_version < KIWI_REQ:
        raise SystemExit('ERROR: Kiwi %s or higher is required'
                         % '.'.join(map(str, KIWI_REQ)))
    elif gobject.pygobject_version > (2, 26, 0):
        # Kiwi is not compatible yet with the changes introduced in
        # http://git.gnome.org/browse/pygobject/commit/?id=84d614
        # Basically, what we do is to revert the changes in _type_register of
        # GObjectMeta at least until kiwi works properly with new pygobject
        from gobject._gobject import type_register

        def _type_register(cls, namespace):
            ## don't register the class if already registered
            if '__gtype__' in namespace:
                return

            if not ('__gproperties__' in namespace or
                    '__gsignals__' in namespace or
                    '__gtype_name__' in namespace):
                return

            # Do not register a new GType for the overrides, as this would sort
            # of defeat the purpose of overrides...
            if cls.__module__.startswith('gi.overrides.'):
                return

            type_register(cls, namespace.get('__gtype_name__'))

        gobject.GObjectMeta._type_register = _type_register

    return True


def init_option_parser(gtk, gst):
    # We should only use the GOption parser if we are already going to
    # import gobject, and if we can find a recent enough version of
    # pygobject on our system. There were bugs in the GOption parsing
    # until pygobject 2.15.0, so just revert to optparse if our
    # pygobject is too old.
    global USE_GOPTION_PARSER
    if not gtk and not gst:
        USE_GOPTION_PARSER = False
    else:
        import gobject
        if getattr(gobject, 'pygobject_version', ()) >= (2, 15, 0):
            USE_GOPTION_PARSER = True
        else:
            USE_GOPTION_PARSER = False


def wrap_for_statprof(main, output_file):
    try:
        import statprof
    except ImportError, e:
        print "Profiling requested, but statprof not available (%s)" % e
        return main

    def wrapped(*args, **kwargs):
        statprof.start()
        try:
            return main(*args, **kwargs)
        finally:
            statprof.stop()
            statprof.display(OUT=file(output_file, 'wb'))
    return wrapped


def wrap_for_builtin_profiler(main, output_file):
    try:
        import cProfile as profile
    except ImportError:
        import profile

    def wrapped(*args, **kwargs):
        prof = profile.Profile()
        try:
            return prof.runcall(main, *args, **kwargs)
        finally:
            prof.dump_stats(output_file)
    return wrapped


def wrap_for_profiling(main):

    def generate_output_file():
        import tempfile
        return os.path.join(tempfile.gettempdir(),
                            'flustat.%s.%s.%d' %
                            (main.__module__, main.__name__, os.getpid()))

    if os.getenv('FLU_PROFILE'):
        return wrap_for_statprof(main, generate_output_file())
    elif os.getenv('FLU_BUILTIN_PROFILE'):
        return wrap_for_builtin_profiler(main, generate_output_file())
    else:
        return main


def boot(path, gtk=False, gst=True, installReactor=True):
    # python 2.5 and twisted < 2.5 don't work together
    pythonMM = sys.version_info[0:2]
    from twisted.copyright import version
    twistedMM = tuple([int(n) for n in version.split('.')[0:2]])
    if pythonMM >= (2, 5) and twistedMM < (2, 5):
        raise SystemError(
            "Twisted versions older than 2.5.0 do not work with "
            "Python 2.5 and newer.  "
            "Please upgrade Twisted or downgrade Python.")

    if gtk or gst:
        init_gobject()

    if gtk:
        init_kiwi()

    if gst:
        from flumotion.configure import configure
        configure.gst_version = init_gst()

    global USE_GTK, USE_GST
    USE_GTK=gtk
    USE_GST=gst
    init_option_parser(gtk, gst)

    # installing the reactor could override our packager's import hooks ...
    if installReactor:
        from twisted.internet import gtk2reactor
        gtk2reactor.install(useGtk=gtk)
    from twisted.internet import reactor

    # ... so we install them again here to be safe
    from flumotion.common import package
    package.getPackager().install()

    # this monkeypatched var exists to let reconnecting factories know
    # when they should warn about a connection being closed, and when
    # they shouldn't because the system is shutting down.
    #
    # there is no race condition here -- the reactor doesn't handle
    # signals until it is run().
    reactor.killed = False

    def setkilled(killed):
        reactor.killed = killed

    reactor.addSystemEventTrigger('before', 'startup', setkilled, False)
    reactor.addSystemEventTrigger('before', 'shutdown', setkilled, True)

    from flumotion.twisted import reflect
    from flumotion.common import errors
    from flumotion.common import setup

    setup.setup()

    from flumotion.common import log
    log.logTwisted()

    main = reflect.namedAny(path)

    wrapped = wrap_for_profiling(main)
    wrapped.__name__ = main.__name__

    try:
        sys.exit(wrapped(sys.argv))
    except (errors.FatalError, SystemError), e:
        safeprintf(sys.stderr, 'ERROR: %s\n', e)
        sys.exit(1)
