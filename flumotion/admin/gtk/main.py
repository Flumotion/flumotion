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

__version__ = "$Rev$"

import os
import sys

import gettext

from twisted.internet import reactor, defer
from flumotion.admin import connections
from flumotion.admin.admin import AdminModel
from flumotion.common import log, errors, connection
from flumotion.configure import configure
from flumotion.twisted import pb as fpb
from flumotion.common.options import OptionParser

# FIXME: a function with a capital is extremely poor style.
def Greeter():
    # We do the import here so gettext has been set up and class strings
    # from greeter are translated
    from flumotion.admin.gtk import greeter
    return greeter.Greeter()

def startAdminFromGreeter(greeter):
    # fuck python's lexicals!
    _info = []

    def got_state(state):
        greeter.set_sensitive(False)
        authenticator = fpb.Authenticator(username=state['user'],
                                          password=state['passwd'])
        info = connection.PBConnectionInfo(state['host'], state['port'],
                                           not state['use_insecure'],
                                           authenticator)
        _info.append(info)
        model = AdminModel()
        return model.connectToManager(info)

    def refused(failure):
        from flumotion.admin.gtk import dialogs
        failure.trap(errors.ConnectionRefusedError)
        dret = dialogs.connection_refused_message(greeter.state['host'],
                                                  greeter.window)
        dret.addCallback(lambda _: startAdminFromGreeter(greeter))
        return dret

    def failed(failure):
        from flumotion.admin.gtk import dialogs
        failure.trap(errors.ConnectionFailedError)
        message = "".join(failure.value.args)
        dret = dialogs.connection_failed_message(_info[0], message,
                                                 greeter.window)
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
    parser = OptionParser(domain="flumotion-admin")
    parser.add_option('-m', '--manager',
                      action="store", type="string", dest="manager",
                      help="the manager to connect to, e.g. localhost:7531")
    parser.add_option('', '--no-ssl',
                      action="store_true", dest="no_ssl",
                      help="disable encryption when connecting to the manager")

    options, args = parser.parse_args(args)

    # set up gettext
    localedir = os.path.join(configure.localedatadir, 'locale')
    log.debug("locale", "Loading locales from %s" % localedir)
    gettext.bindtextdomain('flumotion', localedir)
    gettext.textdomain('flumotion')

    if len(args) > 1:
        log.error('flumotion-admin',
                  'too many arguments: %r' % (args[1:],))

    import gtk.glade
    gtk.glade.bindtextdomain('flumotion', localedir)
    gtk.glade.textdomain('flumotion')

    if options.manager:
        d = startAdminFromManagerString(options.manager,
                                        not options.no_ssl)
    else:
        d = startAdminFromGreeter(Greeter())

    from flumotion.ui.icons import register_icons
    register_icons()

    from flumotion.admin.gtk.client import AdminClientWindow
    win = AdminClientWindow()

    def adminStarted(admin):
        win.setAdminModel(admin)
        win.show()

    def cancel(failure):
        # Cancelled interactively, just quit
        from flumotion.ui.simplewizard import WizardCancelled
        failure.trap(WizardCancelled)
        reactor.stop()

    def failure(failure):
        message = "".join(failure.value.args)
        log.warning('admin', "Failed to connect: %s",
                    log.getFailureMessage(failure))
        sys.stderr.write("Connection to manager failed: %s\n" % message)
        reactor.stop()

    d.addCallbacks(adminStarted, cancel, failure)

    reactor.run()
