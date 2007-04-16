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

import optparse
import os
import sys

import gettext
import gtk.glade

from twisted.internet import reactor, defer
from flumotion.admin import connections
from flumotion.admin.admin import AdminModel
from flumotion.admin.gtk import dialogs
from flumotion.admin.gtk.client import Window
from flumotion.common import log, errors, connection
from flumotion.configure import configure
from flumotion.twisted import pb as fpb

def Greeter():
    # We do the import here so gettext has been set up and class strings
    # from greeter are translated
    from flumotion.admin.gtk import greeter
    return greeter.Greeter()

def startAdminFromGreeter(greeter):
    def got_state(state):
        greeter.set_sensitive(False)
        authenticator = fpb.Authenticator(username=state['user'],
                                          password=state['passwd'])
        info = connection.PBConnectionInfo(state['host'], state['port'],
                                           not state['use_insecure'],
                                           authenticator)
        model = AdminModel()
        return model.connectToManager(info)

    def refused(failure):
        failure.trap(errors.ConnectionRefusedError)
        dret = dialogs.connection_refused_message(greeter.state['host'],
                                                  greeter.window)
        dret.addCallback(lambda _: startAdminFromGreeter(greeter))
        return dret

    def failed(failure):
        failure.trap(errors.ConnectionFailedError)
        message = "".join(failure.value.args)
        dret = dialogs.connection_failed_message(message, greeter.window)
        dret.addCallback(lambda _: startAdminFromGreeter(greeter))
        return dret

    def connected(model):
        greeter.destroy()
        return model

    d = greeter.run_async()
    d.addCallback(got_state)
    d.addCallback(connected)
    d.addErrback(refused)
    d.addErrback(failed)
    return d

def startAdminFromManagerString(managerString, useSSL):
    info = connections.parsePBConnectionInfo(managerString, useSSL)
    model = AdminModel()
    return model.connectToManager(info)

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

    if len(args) > 1:
        log.error('flumotion-admin',
                  'too many arguments: %r' % (args[1:],))

    if options.manager:
        d = startAdminFromManagerString(options.manager,
                                        not options.no_ssl)
    else:
        d = startAdminFromGreeter(Greeter())

    def failure(failure):
        message = "".join(failure.value.args)
        log.warning('admin', "Failed to connect: %s",
                    log.getFailureMessage(failure))
        sys.stderr.write("Connection to manager failed: %s\n" % message)
        reactor.stop()

    d.addCallbacks(lambda model: Window(model).show(), failure)

    reactor.run()
