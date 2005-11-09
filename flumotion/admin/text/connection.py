# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

from flumotion.admin.admin import AdminModel
from flumotion.admin.text.view import AdminTextView
from flumotion.twisted import flavors, reflect
from flumotion.common import errors

from twisted.internet import reactor

def connect_to_manager(stdscr, hostname, port, insecure, username, 
password):
    stdscr.addstr(0,0,"Connecting to %s:%d with username %s " % 
(hostname, port, username))
    stdscr.clrtobot()
    stdscr.refresh()

    model = AdminModel(username, password)
    d = model.connectToHost(hostname, port, insecure)

    def outputError(str):
        print str

    def connected(model):
        stdscr.addstr(0,0,"Connected")
        stdscr.clrtobot()
        stdscr.refresh()

        view = AdminTextView(model, stdscr)
        reactor.addReader(view)
        view.show()

    def refused(failure):
        failure.trap(errors.ConnectionRefusedError)
        #stdscr.addstr(0,0,"Connection refused")
        #stdscr.clrtobot()
        #stdscr.refresh()
        reactor.addSystemEventTrigger('after','shutdown', outputError, "Connection Refused")
        reactor.callLater(0, reactor.stop)

    def failed(failure):
        failure.trap(errors.ConnectionFailedError)
        message = "".join(failure.value.args)
        #stdscr.addstr(0,0,"Connection failed: %s" % message)
        #stdscr.clrtobot()
        #stdscr.refresh()
        reactor.addSystemEventTrigger('after','shutdown', outputError, "Connection Failed: %s" % message)
        reactor.callLater(0, reactor.stop)


    d.addCallback(connected)
    d.addErrback(refused)
    d.addErrback(failed)

