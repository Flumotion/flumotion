# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a video streaming server
# Copyright (C) 2004 Fluendo
# 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import sys

from twisted.internet import reactor
from twisted.manhole import telnet
from twisted.python import log

class Shell(telnet.Shell):
    def telnet_Command(self, cmd):
        if cmd == '\x04' or cmd == 'exit':
            self.transport.loseConnection()
            return
        telnet.Shell.telnet_Command(self, cmd)

if __name__ == '__main__':
    log.startLogging(sys.stdout)
    ts = telnet.ShellFactory()
    ts.protocol = Shell
    reactor.listenTCP(4040, ts)
    reactor.run()
