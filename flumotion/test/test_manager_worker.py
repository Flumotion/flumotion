# -*- Mode: Python; test-case-name: flumotion.test.test_manager_worker -*-
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

from twisted.internet import defer
from twisted.spread import pb

from flumotion.common import log, interfaces
from flumotion.common import testsuite
from flumotion.manager import worker


class FakeTransport:

    def getPeer(self):
        from twisted.internet.address import IPv4Address
        return IPv4Address('TCP', 'nullhost', 1)

    def getHost(self):
        from twisted.internet.address import IPv4Address
        return IPv4Address('TCP', 'nullhost', 1)

    def loseConnection(self):
        pass


class FakeBroker:

    def __init__(self):
        self.transport = FakeTransport()


class FakeMind(log.Loggable):

    def __init__(self, testcase):
        self.broker = FakeBroker()
        self.testcase = testcase

    def notifyOnDisconnect(self, proc):
        pass

    def callRemote(self, name, *args, **kwargs):
        self.debug('callRemote(%s, %r, %r)' % (name, args, kwargs))
        #print "callRemote(%s, %r, %r)" % (name, args, kwargs)
        method = "remote_" + name
        if hasattr(self, method):
            m = getattr(self, method)
            try:
                result = m(*args, **kwargs)
                self.debug('callRemote(%s) succeeded with %r' % (
                    name, result))
                return defer.succeed(result)
            except Exception, e:
                self.warning('callRemote(%s) failed with %s: %s' % (
                    name, str(e.__class__), ", ".join(e.args)))
                return defer.fail(e)
        else:
            raise AttributeError('no method %s on self %r' % (name, self))


class FakeWorkerMind(FakeMind):

    logCategory = 'fakeworkermind'

    def __init__(self, testcase, avatarId):
        FakeMind.__init__(self, testcase)
        self.avatarId = avatarId

    def remote_getPorts(self):
        return (range(7600, 7610), False)

    def remote_getFeedServerPort(self):
        return 7610

    def remote_create(self, avatarId, type, moduleName, methodName, config):
        self.debug('remote_create(%s): logging in component' % avatarId)
        avatar = self.testcase._loginComponent(self.avatarId,
            avatarId, moduleName, methodName, type, config)
        # need to return the avatarId for comparison
        return avatarId


class FakeVishnu:

    def workerAttached(self, avatar):
        pass

    def workerDetached(self, avatar):
        pass


class TestHeaven(testsuite.TestCase):

    def testConstructor(self):
        h = worker.WorkerHeaven(None)
        assert isinstance(h, worker.WorkerHeaven)

    def testAdd(self):

        def gotAvatar(res):
            interface, avatar, cleanup = res
            assert 'foo' in [a.getName() for a in h.getAvatars()]
            assert isinstance(avatar, worker.WorkerAvatar)
            cleanup()
            assert not 'foo' in [a.getName() for a in h.getAvatars()]

        h = worker.WorkerHeaven(FakeVishnu())
        mind = FakeWorkerMind(self, 'testworker')
        from flumotion.manager.manager import Dispatcher
        dispatcher = Dispatcher(lambda x, y: defer.succeed(None))
        dispatcher.registerHeaven(h, interfaces.IWorkerMedium)
        d = dispatcher.requestAvatar('foo', None, mind, pb.IPerspective,
                                     interfaces.IWorkerMedium)
        d.addCallback(gotAvatar)
        return d
