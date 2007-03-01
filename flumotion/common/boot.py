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

import os
import sys

PYGTK_REQ = (2, 6, 3)

GST_REQ = {'0.10': {'gstreamer': (0, 10, 0, 1),
                    'gst-python': (0, 10, 0, 1)}}

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
        raise SystemExit('ERROR: Expected GStreamer %s, but got incompatible %s'
                         % (gst_majorminor, tup2version(gst_version[:2])))
    
    if gst_version < gst_req:
        raise SystemExit('ERROR: GStreamer %s too old; install %s or newer'
                         % (tup2version(gst_version), tup2version(gst_req)))

    if pygst_version < pygst_req:
        raise SystemExit('ERROR: gst-python %s too old; install %s or newer'
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
                             '(looking for versions %r)' % (GST_REQ.keys(),))

    return gst_majorminor

def boot(path, gtk=False, gst=True, installReactor=True):
    if gtk or gst:
        init_gobject()

    if gst:
        from flumotion.configure import configure
        configure.gst_version = init_gst()

    # installing the reactor could override our packager's import hooks ...
    if installReactor:
        from twisted.internet import gtk2reactor
        gtk2reactor.install(useGtk=gtk)
        # this monkeypatched var exists to let reconnecting factories know
        # when they should warn about a connection being closed, and when
        # they shouldn't because the system is shutting down.
        # 
        # there is no race condition here -- the reactor doesn't handle
        # signals until it is run().
        from twisted.internet import reactor
        reactor.killed = False
        def setkilled(killed):
            reactor.killed = killed
        reactor.addSystemEventTrigger('before', 'startup', setkilled, False)
        reactor.addSystemEventTrigger('before', 'shutdown', setkilled, True)



    # ... so we install them again here to be safe
    from flumotion.common import package
    package.getPackager().install()

    from flumotion.twisted import reflect
    from flumotion.common import errors
    from flumotion.common import setup

    setup.setup()

    from flumotion.common import log
    log.logTwisted()

    # we redefine catching
    __pychecker__ = 'no-reuseattr'

    if os.getenv('FLU_PROFILE'):
        def catching(proc, *args, **kwargs):
            import statprof
            statprof.start()
            try:
                return proc(*args, **kwargs)
            finally:
                statprof.stop()
                statprof.display()
    elif os.getenv('FLU_ATEXIT'):
        def catching(proc, *args, **kwargs):
            env = os.getenv('FLU_ATEXIT').split(' ')
            fqfn = env.pop(0)
            log.info('atexit', 'FLU_ATEXIT set, will call %s(*%r) on exit',
                     fqfn, env)
            atexitproc = reflect.namedAny(fqfn)

            try:
                return proc(*args, **kwargs)
            finally:
                log.info('atexit', 'trying to call %r(*%r)',
                         atexitproc, env)
                atexitproc(*env)
    else:
        def catching(proc, *args, **kwargs):
            return proc(*args, **kwargs)
        
    main = reflect.namedAny(path)
    
    try:
        sys.exit(catching(main, sys.argv))
    except errors.SystemError, e:
        print 'ERROR:', e
        sys.exit(1)
