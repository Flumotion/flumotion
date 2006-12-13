# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006 Fluendo, S.L. (www.fluendo.com).
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

import optparse
import os
import sys

import gettext
import gtk.glade

from twisted.internet import reactor
from flumotion.admin import connections
from flumotion.admin.admin import AdminModel
from flumotion.admin.gtk import dialogs
from flumotion.admin.gtk.client import Window
from flumotion.common import log, errors
from flumotion.configure import configure
from flumotion.twisted import pb as fpb

def _runInterface(conf_file, options, thegreeter=None):
    if conf_file:
        # load the conf file here
        raise NotImplementedError()

    d = None
    g = None
    if options and options.manager:
        info = connections.parsePBConnectionInfo(options.manager,
                                                 not options.no_ssl)
        model = AdminModel(info.authenticator)
        d = model.connectToHost(info.host, info.port, not info.use_ssl)
    else:
        # We do the import here so gettext has been set up and class strings
        # from greeter are translated
        from flumotion.admin.gtk import greeter
        g = thegreeter or greeter.Greeter()
        state = g.run()
        if not state:
            reactor.callLater(0, reactor.stop)
            return
        g.set_sensitive(False)

        authenticator = fpb.Authenticator(username=state['user'],
                                          password=state['passwd'])
        model = AdminModel(authenticator)
        d = model.connectToHost(state['host'], state['port'], state['use_insecure'])

    def connected(model, greeter):
        if greeter:
            greeter.destroy()
        Window(model).show()

    def refused(failure, greeter):
        failure.trap(errors.ConnectionRefusedError)
        if greeter:
            dret = dialogs.connection_refused_message(state['host'],
                                                      greeter.window)
            dret.addCallback(lambda _: _runInterface(None, None, greeter))
        else:
            log.error("Manager refused connection.")

    def failed(failure, greeter):
        failure.trap(errors.ConnectionFailedError)
        message = "".join(failure.value.args)
        if greeter:
            dret = dialogs.connection_failed_message(message, greeter.window)
            dret.addCallback(lambda _: _runInterface(None, None, greeter))
        else:
            log.error("Connection to manager failed: %s", message)

    d.addCallback(connected, g)
    d.addErrback(refused, g)
    d.addErrback(failed, g)

def main(args):
    parser = optparse.OptionParser()
    parser.add_option('-d', '--debug',
                      action="store", type="string", dest="debug",
                      help="set debug levels")
    parser.add_option('-v', '--verbose',
                      action="store_true", dest="verbose",
                      help="be verbose")
    parser.add_option('', '--version',
                      action="store_true", dest="version",
                      default=False,
                      help="show version information")
    parser.add_option('-m', '--manager',
                      action="store", type="string", dest="manager",
                      help="the manager to connect to, e.g. localhost:7531")
    parser.add_option('', '--no-ssl',
                      action="store_true", dest="no_ssl",
                      help="disable encryption when connecting to the manager")
 
    options, args = parser.parse_args(args)

    if options.version:
        from flumotion.common import common
        print common.version("flumotion-admin")
        return 0

    if options.verbose:
        log.setFluDebug("*:3")

    if options.debug:
        log.setFluDebug(options.debug)

    # set up gettext
    localedir = os.path.join(configure.localedatadir, 'locale')
    log.debug("locale", "Loading locales from %s" % localedir)
    gettext.bindtextdomain('flumotion', localedir)
    gettext.textdomain('flumotion')
    gtk.glade.bindtextdomain('flumotion', localedir)
    gtk.glade.textdomain('flumotion')

    conf_files = args[1:]

    if conf_files and len(conf_files) > 1:
        log.error('flumotion-admin',
            'too many configuration files: %r' % conf_files)

    elif conf_files:
        _runInterface(conf_files[0], options)
    else:
        _runInterface(None, options)

    reactor.run()
