# -*- Mode: Python; test-case-name:flumotion.test.test_worker_worker -*-
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

import common
from twisted.trial import unittest

from twisted.internet import reactor

from flumotion.worker import worker

class TestKid(unittest.TestCase):
    def testGetPid(self):
        kid = worker.Kid(1092, "kid", "http", "module", "method", {},
            [('belgian', '/opt/ion/al'), ('american', '/ess/en/tial')])
        self.assertEquals(kid.avatarId, "kid")
        self.assertEquals(kid.type, "http")
        self.assertEquals(kid.config, {})
        self.assertEquals(len(kid.bundles), 2)

        self.assertEquals(kid.getPid(), 1092)

class TestKindergarten(unittest.TestCase):
    def testInit(self):
        k = worker.Kindergarten({}, "")
        self.assertEquals(k.options, {})
        self.assertEquals(k.kids, {})
        self.assert_(k.program)

    def testRemoveKidByPid(self):
        k = worker.Kindergarten({}, "")
        k.kids['/swede/johan'] = worker.Kid(1, "/swede/johan", "http",
            "module", "method", {}, [('foo', 'bar')])

        self.assertEquals(k.removeKidByPid(2), False)

        self.assertEquals(k.removeKidByPid(1), True)
        self.assertEquals(k.kids, {})

class FakeOptions:
    def __init__(self):
        self.host = 'localhost'
        self.port = 9999
        self.transport = 'TCP'
        self.feederports = []
        self.name = 'fakeworker'
    
class TestWorkerClientFactory(unittest.TestCase):
    def testInit(self):
        brain = worker.WorkerBrain(FakeOptions())
        factory = worker.WorkerClientFactory(brain)

        unittest.deferredResult(brain.teardown())

class FakeRef:
    def notifyOnDisconnect(self, callback):
        pass

class TestWorkerMedium(unittest.TestCase):
    def testSetRemoteReference(self):
        brain = worker.WorkerBrain(FakeOptions())
        self.medium = worker.WorkerMedium(brain, [])
        self.medium.setRemoteReference(FakeRef())
        self.assert_(self.medium.hasRemoteReference())

        unittest.deferredResult(brain.teardown())

# FIXME: add tests to test signal handler ? Might not be so easy.
