# -*- Mode: Python; test-case-name: flumotion.test.test_flavors -*-
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

import common

from twisted.trial import unittest

from twisted.internet import reactor
from twisted.spread import pb
from flumotion.twisted import flavors

class TestStateCacheable(flavors.StateCacheable):
    pass
class TestStateRemoteCache(flavors.StateRemoteCache):
    pass

pb.setUnjellyableForClass(TestStateCacheable, TestStateRemoteCache)

class FakeObject: pass
class FakeListener:
    # listener interface
    __implements__ = flavors.IStateListener,
    
    def stateSet(self, state, key, value): pass
    def stateAppend(self, state, key, value): pass
    def stateRemove(self, state, key, value): pass

class TestRoot(pb.Root):
    def remote_getState(self):
        self.state = TestStateCacheable()
        self.state.addKey('name', 'lois')
        self.state.addListKey('children')
        return self.state

    def remote_setStateName(self, name):
        self.state.set('name', name)

    def remote_bearChild(self, name):
        self.state.append('children', name)

    def remote_haveAdopted(self, name):
        self.state.remove('children', name)

class TestStateSet(unittest.TestCase):
    def setUp(self):
        self.changes = []

    # helper functions to start PB comms
    def runClient(self):
        f = pb.PBClientFactory()
        reactor.connectTCP("127.0.0.1", self.port, f)
        d = f.getRootObject()
        d.addCallback(self.clientConnected)
        return d
        #.addCallbacks(self.connected, self.notConnected)
        # self.id = reactor.callLater(10, self.timeOut)

    def clientConnected(self, perspective):
        self.perspective = perspective

    def runServer(self):
        factory = pb.PBServerFactory(TestRoot())
        factory.unsafeTracebacks = 1
        p = reactor.listenTCP(0, factory, interface="127.0.0.1")
        self.port = p.getHost().port

    # actual tests
    def testStateSet(self):
        # start everything
        self.runServer()
        d = self.runClient()
        unittest.deferredResult(d)
        
        # get the state
        d = self.perspective.callRemote('getState')
        state = unittest.deferredResult(d)

        self.failUnless(state)
        self.failUnlessEqual(state.get('name'), 'lois')
        self.assertRaises(KeyError, state.get, 'dad')

        # ask server to set the name
        d = self.perspective.callRemote('setStateName', 'clark')
        r = unittest.deferredResult(d)

        self.failUnlessEqual(state.get('name'), 'clark')

    def testStateAppendRemove(self):
        # start everything
        self.runServer()
        d = self.runClient()
        unittest.deferredResult(d)
        
        # get the state
        d = self.perspective.callRemote('getState')
        state = unittest.deferredResult(d)

        self.failUnless(state)
        self.failUnlessEqual(state.get('children'), [])

        # ask server to make children
        d = self.perspective.callRemote('bearChild', 'robin')
        r = unittest.deferredResult(d)

        self.failUnlessEqual(state.get('children'), ['robin'])

        # lists can have same member more than once
        d = self.perspective.callRemote('bearChild', 'robin')
        r = unittest.deferredResult(d)

        self.failUnlessEqual(state.get('children'), ['robin', 'robin'])

        # give one of them away
        d = self.perspective.callRemote('haveAdopted', 'robin')
        r = unittest.deferredResult(d)

        self.failUnlessEqual(state.get('children'), ['robin'])

        # add a different one
        d = self.perspective.callRemote('bearChild', 'batman')
        r = unittest.deferredResult(d)

        self.failUnlessEqual(state.get('children'), ['robin', 'batman'])

    def testStateWrongListener(self):
        # start everything
        self.runServer()
        d = self.runClient()
        unittest.deferredResult(d)

        # get the state
        d = self.perspective.callRemote('getState')
        state = unittest.deferredResult(d)

        self.assertRaises(NotImplementedError, state.addListener, FakeObject())
        self.assertRaises(NotImplementedError, state.removeListener,
            FakeObject())
        self.assertRaises(KeyError, state.removeListener, FakeListener())

    # listener interface
    __implements__ = flavors.IStateListener,
    
    def stateSet(self, state, key, value):
        self.changes.append(('set', state, key, value))

    def stateAppend(self, state, key, value):
        self.changes.append(('append', state, key, value))

    def stateRemove(self, state, key, value):
        self.changes.append(('remove', state, key, value))

    # listener tests
    def testStateSetListener(self):
        # start everything
        self.runServer()
        d = self.runClient()
        unittest.deferredResult(d)

        # get the state
        d = self.perspective.callRemote('getState')
        state = unittest.deferredResult(d)

        state.addListener(self)

         # ask server to set the name
        d = self.perspective.callRemote('setStateName', 'robin')
        r = unittest.deferredResult(d)
        c = self.changes.pop()
        self.failUnlessEqual(c, ('set', state, 'name', 'robin'))

    def testStateAppendRemoveListener(self):
        # start everything
        self.runServer()
        d = self.runClient()
        unittest.deferredResult(d)
        
        # get the state
        d = self.perspective.callRemote('getState')
        state = unittest.deferredResult(d)

        state.addListener(self)

        # ask server to make children
        d = self.perspective.callRemote('bearChild', 'robin')
        r = unittest.deferredResult(d)

        c = self.changes.pop()
        self.failUnlessEqual(c, ('append', state, 'children', 'robin'))

        # lists can have same member more than once
        d = self.perspective.callRemote('bearChild', 'robin')
        r = unittest.deferredResult(d)

        c = self.changes.pop()
        self.failUnlessEqual(c, ('append', state, 'children', 'robin'))

        # give one of them away
        d = self.perspective.callRemote('haveAdopted', 'robin')
        r = unittest.deferredResult(d)

        c = self.changes.pop()
        self.failUnlessEqual(c, ('remove', state, 'children', 'robin'))

        # add a different one
        d = self.perspective.callRemote('bearChild', 'batman')
        r = unittest.deferredResult(d)

        c = self.changes.pop()
        self.failUnlessEqual(c, ('append', state, 'children', 'batman'))

class TestState(unittest.TestCase):
    def testStateAddKey(self):
        c = flavors.StateCacheable()

        c.addListKey('list')
        self.failUnless(c.hasKey('list'))
        self.failIf(c.hasKey('randomkey'))
        l = c.get('list')
        self.failUnlessEqual(len(l), 0)
        c.append('list', 'item')
        l = c.get('list')
        self.failUnlessEqual(len(l), 1)
        self.failUnlessEqual(l[0], 'item')

        c.addListKey('two')
        l = c.get('two')
        self.failUnlessEqual(len(l), 0)
        c.append('two', 'B')
        l = c.get('two')
        self.assertEqual(len(l), 1)
        self.assertEqual(l[0], 'B')
        
    def testStateGet(self):
        c = flavors.StateCacheable()

        c.addKey('akey')
        c.set('akey', 'avalue')
        self.assertEquals(c.get('akey'), 'avalue')
        self.assertRaises(KeyError, c.get, 'randomkey')
  
    def testStateAppendRemove(self):
        c = flavors.StateCacheable()

        c.addListKey('alist')

        c.append('alist', 'avalue')
        self.assertEquals(c.get('alist'), ['avalue', ])
        self.assertRaises(KeyError, c.append, 'randomlistkey', 'value')

        c.remove('alist', 'avalue')
        self.assertEquals(c.get('alist'), [])
        self.assertRaises(KeyError, c.remove, 'randomlistkey', 'value')
        self.assertRaises(ValueError, c.remove, 'alist', 'value')
  
if __name__ == '__main__':
    unittest.main()
