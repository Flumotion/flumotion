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

import os
import sys

import flumotion.common.setup

#sys.path.insert(1, os.path.abspath('..'))

#import pygtk
#pygtk.require('2.0')

#import gst
#import gst.interfaces

#ltihooks = sys.modules.get('gst.ltihooks')
#if ltihooks:
#    ltihooks.uninstall()

# logging
flumotion.common.setup.setup()

from twisted.internet import reactor
from twisted.spread import pb

# test objects to be used in unittests to simulate the processes
# subclass them to add your own methods

class TestAdmin(pb.Referenceable):
    def run(self, port):
        self.perspective = None # perspective on the manager's PB server
        f = pb.PBClientFactory()
        reactor.connectTCP("127.0.0.1", port, f)
        d = f.getRootObject()
        d.addCallback(self._gotRootObject)
        return d

    def _gotRootObject(self, perspective):
        self.perspective = perspective
        return perspective.callRemote('identify', 'admin', self)

class TestWorker(pb.Referenceable):
    def run(self, port):
        f = pb.PBClientFactory()
        reactor.connectTCP("127.0.0.1", port, f)
        d = f.getRootObject()
        d.addCallback(self._gotRootObject)
        return d

    def _gotRootObject(self, perspective):
        self.perspective = perspective
        return perspective.callRemote('identify', 'worker', self)

class TestManagerRoot(pb.Root):
    def remote_identify(self, who, reference):
        key = who + 'Reference'
        setattr(self, key, reference)

class TestManager:
    def run(self, rootClass):
        """
        Run the test manager.  Return port it is listening on.
        """
        factory = pb.PBServerFactory(rootClass())
        factory.unsafeTracebacks = 1
        p = reactor.listenTCP(0, factory, interface="127.0.0.1")
        port = p.getHost().port
        return port
