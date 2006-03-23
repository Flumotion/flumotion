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

from flumotion.extern.fdpass import fdpass

from twisted.internet import unix
from twisted.python import log

# Heavily based on 
# http://twistedmatrix.com/trac/browser/sandbox/exarkun/copyover/server.py
# and client.py
# Thanks for the inspiration!
class FDServer (unix.Server):
    def sendFileDescriptor (self, fileno, data="\0"):
        return fdpass.writefds(self.fileno(), [fileno], data)

class FDPort (unix.Port):
    transport = FDServer

class FDClient (unix.Client):
    def doRead(self):
        if not self.connected:
            return
        try:
            (fds, message) = fdpass.readfds(self.fileno(), 64*1024)
        except:
            log.msg('recvmsg():')
            log.err()
        else:
            try:
                # Sometimes we get a read with no data or control messages. 
                # Ignore those. 
                if len(fds) > 0:
                    self.protocol.fileDescriptorsReceived(fds, message)
                elif len(message) > 0:
                    self.protocol.dataReceived(message)
            except:
                log.msg('protocol.fileDescriptorsReceived')
                log.err()
        return unix.Client.doRead(self)

class FDConnector (unix.Connector):
    def _makeTransport(self):
        return FDClient (self.address, self, self.reactor)

