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

"""flumotion-admin-text entry point, command line parsing and invokation"""

import curses

from twisted.internet import reactor

from flumotion.admin.text import connection
from flumotion.admin.text.greeter import AdminTextGreeter
from flumotion.common import messages # make Message proxyable
from flumotion.common.options import OptionParser
from flumotion.common.connection import PBConnectionInfo
from flumotion.twisted import pb as fpb

__version__ = "$Rev$"


def cleanup_curses(stdscr):
    curses.nocbreak()
    stdscr.keypad(0)
    curses.echo()
    curses.endwin()


def _runInterface(options):
    # initialise curses

    stdscr = curses.initscr()
    curses.noecho()
    curses.cbreak()
    stdscr.nodelay(1)
    stdscr.keypad(1)

    reactor.addSystemEventTrigger('after',
                                  'shutdown', cleanup_curses, stdscr)


    # first lets sort out logging in
    username = 'user'
    password = 'test'
    hostname = 'localhost'
    insecure = False
    port = 7531
    if options.username and options.password and options.hostname:
        username = options.username
        password = options.password
        hostname = options.hostname
        if options.port:
            try:
                port = int(options.port)
            except ValueError:
                pass
        if options.insecure:
            insecure = True
        authenticator = fpb.Authenticator(username=username, password=password)
        info = PBConnectionInfo(hostname, port, not insecure, authenticator)
        connection.connect_to_manager(stdscr, info)

    else:
        # do greeter
        # get recent connections
        greeter = AdminTextGreeter(stdscr)
        reactor.addReader(greeter)
        greeter.show()


def main(args):
    parser = OptionParser(domain="flumotion-admin-text")
    parser.add_option('-u', '--username',
                      action="store", type="string", dest="username",
                      help="set username to connect to manager")
    parser.add_option('-P', '--password',
                      action="store", type="string", dest="password",
                      help="set password to connect to manager")
    parser.add_option('-H', '--hostname',
                      action="store", type="string", dest="hostname",
                      help="set hostname of manager to connect to")
    parser.add_option('-p', '--port',
                      action="store", type="string", dest="port",
                      help="set port of manager to connect to")
    parser.add_option('', '--insecure',
                      action="store_true", dest="insecure",
                      help="make insecure connection")

    options, args = parser.parse_args(args)

    _runInterface(options)

    reactor.run()
