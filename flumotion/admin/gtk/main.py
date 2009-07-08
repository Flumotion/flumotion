# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
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

"""flumotion-admin entry point, command line parsing and invokation"""

import gettext
import sys

from twisted.internet import reactor
from twisted.python import log as twistedlog

from flumotion.admin.connections import parsePBConnectionInfoRecent
from flumotion.common import log, i18n
from flumotion.common.errors import  OptionError, ConnectionRefusedError,\
        ConnectionFailedError
from flumotion.common.options import OptionParser

__version__ = "$Rev$"
_ = gettext.gettext
_retval = 0


def showGreeter(adminWindow):
    from flumotion.admin.gtk.greeter import Greeter
    greeter = Greeter(adminWindow)
    d = greeter.runAsync()
    return d


def _connectToManager(win, manager, ssl):
    try:
        info = parsePBConnectionInfoRecent(manager, use_ssl=ssl)
    except OptionError, e:
        raise SystemExit("ERROR: %s" % (e, ))

    def errback(failure):
        global _retval
        print >> sys.stderr, "ERROR: %s" % (failure.value, )
        _retval = 1
        reactor.stop()

    def errorDialogShown(unused):
        return showGreeter(win)

    def connectionFailed(failure):
        failure.trap(ConnectionRefusedError, ConnectionFailedError)
        from flumotion.admin.gtk.dialogs import showConnectionErrorDialog
        d = showConnectionErrorDialog(failure, info)
        d.addCallback(errorDialogShown)
        return d

    d = win.openConnection(info)
    d.addErrback(connectionFailed)
    d.addErrback(errback)
    return d


def main(args):
    global _retval

    parser = OptionParser(domain="flumotion-admin")
    parser.add_option('-m', '--manager',
                      action="store", type="string", dest="manager",
                      help="the manager to connect to, e.g. localhost:7531")
    parser.add_option('', '--no-ssl',
                      action="store_false", dest="ssl", default=True,
                      help="disable encryption when connecting to the manager")

    options, args = parser.parse_args(args)

    i18n.installGettext()

    if len(args) > 1:
        log.error('flumotion-admin',
                  'too many arguments: %r' % (args[1:], ))
        return 1

    from flumotion.ui.icons import register_icons
    register_icons()

    from flumotion.admin.gtk.dialogs import exceptionHandler
    sys.excepthook = exceptionHandler

    from flumotion.admin.gtk.adminwindow import AdminWindow
    win = AdminWindow()

    if options.verbose or (options.debug and options.debug > 3):
        win.setDebugEnabled(True)

    if options.manager:
        d = _connectToManager(win, options.manager, options.ssl)
    else:
        d = showGreeter(win)

    # Printout unhandled exception to stderr
    d.addErrback(twistedlog.err)

    # Fixes a bug on widnows version of twisted that makes
    # the application to crash because _simtag is not defined.
    if not hasattr(reactor, '_simtag'):
        reactor._simtag = None

    reactor.run()
    return _retval
