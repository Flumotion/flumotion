# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/twisted/shell.py: do cool stuff from a shell
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo (www.fluendo.com)

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# See "LICENSE.GPL" in the source distribution for more information.

# This program is also licensed under the Flumotion license.
# See "LICENSE.Flumotion" in the source distribution for more information.

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
