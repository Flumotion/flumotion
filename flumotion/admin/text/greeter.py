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

"""interface displayed when you first run the cursor interface"""

import curses

import gobject
from twisted.internet import reactor
from zope.interface import implements

from flumotion.admin.connections import getRecentConnections
from flumotion.admin.text import misc_curses
from flumotion.admin.text import connection
from flumotion.common.connection import PBConnectionInfo
from flumotion.common import log
from flumotion.twisted import flavors, pb as fpb

__version__ = "$Rev$"


class AdminTextGreeter(log.Loggable, gobject.GObject, misc_curses.CursesStdIO):
    implements(flavors.IStateListener)

    logCategory = 'admintextgreeter'

    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.connections = getRecentConnections()
        self.current_connection = 0
        self.state = 0
        self.current_input = ''
        curses.curs_set(0)
        self.entries = ['', 'Hostname', 'Port', 'Secure?',
                         'Username', 'Password']
        self.inputs = ['', 'localhost', '7531', 'Yes', 'user', '']

    def show(self):
        self.stdscr.addstr(0, 0, "Please choose a connection:")

        cury = 3
        maxyx = self.stdscr.getmaxyx()
        self.debug("mayx: %d, %d", maxyx[0], maxyx[1])
        for c in self.connections:
            self.debug("cury: %d", cury)
            if cury - 3 == self.current_connection:
                self.stdscr.addstr(cury, 10, c.name, curses.A_REVERSE)
            else:
                self.stdscr.addstr(cury, 10, c.name)
            if cury + 10 > maxyx[0]:
                break
            cury = cury + 1
        self.displayed_connections = cury - 3
        if cury - 3 == self.current_connection:
            self.stdscr.addstr(cury + 1, 10, "New connection...",
                               curses.A_REVERSE)
        else:
            self.stdscr.addstr(cury + 1, 10, "New connection...")
        self.stdscr.refresh()


    def display_current_input_line(self):
        cury = self.displayed_connections + 5 + self.state
        if self.state > 0 and self.state < 5:
            self.stdscr.addstr(cury, 10, "%s: %s" % (self.entries[self.state],
                                                     self.current_input))
        elif self.state == 5:
            # password entry
            self.stdscr.addstr(cury, 10, "%s: " % self.entries[self.state])
        else:
            self.stdscr.move(cury, 10)
        self.stdscr.clrtobot()
        self.stdscr.refresh()

    def connectionLost(self, failure):
        pass

    def doRead(self):
        c= self.stdscr.getch()
        if self.state == 0:
            if c == curses.KEY_DOWN:
                if self.current_connection >= self.displayed_connections:
                    self.current_connection = 0
                else:
                    self.current_connection = self.current_connection + 1
                self.show()
            elif c == curses.KEY_UP:
                if self.current_connection == 0:
                    self.current_connection = self.displayed_connections
                else:
                    self.current_connection = self.current_connection - 1
                self.show()
            elif c == curses.KEY_ENTER or c == 10:
                # if new connection, ask for username, password, hostname etc.
                if self.current_connection == self.displayed_connections:
                    curses.curs_set(1)
                    self.current_input = self.inputs[1]
                    self.state = 1
                    self.display_current_input_line()
                else:
                    # ok a recent connection has been selected
                    curses.curs_set(1)
                    c = self.connections[self.current_connection]
                    info = c.info
                    reactor.removeReader(self)
                    connection.connect_to_manager(self.stdscr, info)
        else:
            if c == curses.KEY_ENTER or c == 10:
                if self.state < 6:
                    self.inputs[self.state] = self.current_input
                if self.state < 5:
                    self.current_input = self.inputs[self.state+1]
                    self.state = self.state + 1
                    self.display_current_input_line()
                else:
                    # connect
                    reactor.removeReader(self)
                    try:
                        port = int(self.inputs[2])
                    except ValueError:
                        port = 7531
                    info = PBConnectionInfo(self.inputs[1], port,
                      self.inputs[3] == 'Yes', fpb.Authenticator(
                        username=self.inputs[4], password=self.inputs[5]))

                    connection.connect_to_manager(self.stdscr, info)
                    pass
            elif c == curses.KEY_BACKSPACE or c == 127:
                self.current_input = self.current_input[:-1]
                self.display_current_input_line()
            elif c == curses.KEY_UP:
                if self.state > 0:
                    self.current_input = self.inputs[self.state-1]
                    self.state = self.state - 1
                if self.state == 0:
                    # turn off cursor
                    curses.curs_set(0)
                self.display_current_input_line()
            elif c == curses.KEY_DOWN:
                pass
            else:
                self.current_input = self.current_input + chr(c)
                self.display_current_input_line()
