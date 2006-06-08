# -*- Mode: Python; test-case-name: flumotion.test.test_flavors -*-
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
import testclasses
import twisted
import twisted.copyright #T1.3

from twisted.trial import unittest

from twisted.internet import reactor, defer
from twisted.spread import pb
from flumotion.twisted import flavors
from flumotion.twisted.compat import implements
#T1.3
def weHaveAnOldTwisted():
    return twisted.copyright.version < '2.0.0'

class TestStateCacheable(flavors.StateCacheable):
    pass
class TestStateRemoteCache(flavors.StateRemoteCache):
    pass

pb.setUnjellyableForClass(TestStateCacheable, TestStateRemoteCache)

class FakeObject: pass
class FakeListener:
    # listener interface
    implements(flavors.IStateListener)
    
    def stateSet(self, state, key, value): pass
    def stateAppend(self, state, key, value): pass
    def stateRemove(self, state, key, value): pass

class TestRoot(testclasses.TestManagerRoot):
    def remote_getState(self):
        self.state = TestStateCacheable()
        self.state.addKey('name', 'lois')
        self.state.addListKey('children')
        return self.state

    def remote_setStateName(self, name):
        return self.state.set('name', name)

    def remote_bearChild(self, name):
        return self.state.append('children', name)

    def remote_haveAdopted(self, name):
        return self.state.remove('children', name)

class TestStateSet(unittest.TestCase):
    def setUp(self):
        self.changes = []
        self.runServer()

    def tearDown(self):
        return self.stopServer()
        
    # helper functions to start PB comms
    def runClient(self):
        f = pb.PBClientFactory()
        self.cport = reactor.connectTCP("127.0.0.1", self.port, f)
        d = f.getRootObject()
        d.addCallback(self.clientConnected)
        if weHaveAnOldTwisted():
            reactor.iterate()
        return d
        #.addCallbacks(self.connected, self.notConnected)
        # self.id = reactor.callLater(10, self.timeOut)

    def clientConnected(self, perspective):
        self.perspective = perspective
        self._dDisconnect = defer.Deferred()
        perspective.notifyOnDisconnect(
            lambda r: self._dDisconnect.callback(None))

    def stopClient(self):
        self.cport.disconnect()
        return self._dDisconnect

    def runServer(self):
        factory = pb.PBServerFactory(TestRoot())
        factory.unsafeTracebacks = 1
        self.sport = reactor.listenTCP(0, factory, interface="127.0.0.1")
        self.port = self.sport.getHost().port

    def stopServer(self):
        return self.sport.stopListening()

    # actual tests
    def testStateSet(self):
        d = self.runClient()
        d.addCallback(lambda _: self.perspective.callRemote('getState'))

        def set_state(state):
            d.state = state
            self.failUnless(state)
            self.failUnlessEqual(state.get('name'), 'lois')
            self.assertRaises(KeyError, state.get, 'dad')
            return self.perspective.callRemote('setStateName', 'clark')

        def check_name(_):
            self.failUnlessEqual(d.state.get('name'), 'clark')

        d.addCallback(set_state)
        d.addCallback(check_name)
        d.addCallback(lambda _: self.stopClient())
        if weHaveAnOldTwisted(): #T1.3
            return unittest.deferredResult(d)
        else:
            return d

    def testStateAppendRemove(self):
        # start everything
        d = self.runClient()
        d.addCallback(lambda _: self.perspective.callRemote('getState'))

        def set_state_and_bear_child(state):
            d.state = state
            self.failUnless(state)
            self.failUnlessEqual(state.get('children'), [])
            return self.perspective.callRemote('bearChild', 'robin')

        def check_first_kid_and_bear_again(_):
            self.failUnlessEqual(d.state.get('children'), ['robin'])
            return self.perspective.callRemote('bearChild', 'robin')

        def check_second_kid_and_give_away(_):
            self.failUnlessEqual(d.state.get('children'), ['robin', 'robin'])
            return self.perspective.callRemote('haveAdopted', 'robin')

        def check_after_adopt_and_bear_again(_):
            self.failUnlessEqual(d.state.get('children'), ['robin'])
            return self.perspective.callRemote('bearChild', 'batman')

        def check_third_kid_and_stop(_):
            self.failUnlessEqual(d.state.get('children'), ['robin', 'batman'])
            return self.stopClient()

        d.addCallback(set_state_and_bear_child)
        d.addCallback(check_first_kid_and_bear_again)
        d.addCallback(check_second_kid_and_give_away)
        d.addCallback(check_after_adopt_and_bear_again)
        d.addCallback(check_third_kid_and_stop)
        if weHaveAnOldTwisted(): #T1.3
            return unittest.deferredResult(d)
        else:
            return d

    def testStateWrongListener(self):
        # start everything
        d = self.runClient()
        d.addCallback(lambda _: self.perspective.callRemote('getState'))

        def got_state_and_stop(state):
            self.assertRaises(NotImplementedError, state.addListener, FakeObject())
            self.assertRaises(NotImplementedError, state.removeListener,
                              FakeObject())
            self.assertRaises(KeyError, state.removeListener, FakeListener())
            return self.stopClient()

        d.addCallback(got_state_and_stop)
        if weHaveAnOldTwisted(): #T1.3
            return unittest.deferredResult(d)
        else:
            return d

    # listener interface
    implements(flavors.IStateListener)
    
    def stateSet(self, state, key, value):
        self.changes.append(('set', state, key, value))

    def stateAppend(self, state, key, value):
        self.changes.append(('append', state, key, value))

    def stateRemove(self, state, key, value):
        self.changes.append(('remove', state, key, value))

    # listener tests
    def testStateSetListener(self):
        # start everything and get the state
        d = self.runClient()
        d.addCallback(lambda _: self.perspective.callRemote('getState'))

        # ask server to set the name
        def add_listener_and_set_name(state):
            d.state = state # monkeypatch
            state.addListener(self)
            return self.perspective.callRemote('setStateName', 'robin')

        def check_results(_):
            c = self.changes.pop()
            self.failUnlessEqual(c, ('set', d.state, 'name', 'robin'))
            return self.stopClient()

        d.addCallback(add_listener_and_set_name)
        d.addCallback(check_results)
        if weHaveAnOldTwisted(): #T1.3
            return unittest.deferredResult(d)
        else:
            return d

    def testStateAppendRemoveListener(self):
        # start everything and get the state
        d = self.runClient()
        d.addCallback(lambda _: self.perspective.callRemote('getState'))

        def add_listener_and_bear_child(state):
            d.state = state # monkeypatch
            state.addListener(self)
            return self.perspective.callRemote('bearChild', 'robin')

        def check_append_results_and_adopt_kid(_):
            c = self.changes.pop()
            self.failUnlessEqual(c, ('append', d.state, 'children', 'robin'))
            return self.perspective.callRemote('haveAdopted', 'robin')

        def check_remove_results_and_bear_child(_):
            c = self.changes.pop()
            self.failUnlessEqual(c, ('remove', d.state, 'children', 'robin'))
            return self.perspective.callRemote('bearChild', 'batman')

        def check_append_results_and_stop(_):
            c = self.changes.pop()
            self.failUnlessEqual(c, ('append', d.state, 'children', 'batman'))
            return self.stopClient()

        d.addCallback(add_listener_and_bear_child)
        d.addCallback(check_append_results_and_adopt_kid)
        d.addCallback(check_remove_results_and_bear_child)
        d.addCallback(check_append_results_and_stop)
        if weHaveAnOldTwisted(): #T1.3
            return unittest.deferredResult(d)
        else:
            return d

class TestFullListener(unittest.TestCase):
    def setUp(self):
        self.changes = []
        self.runServer()

    def tearDown(self):
        return self.stopServer()
        
    # helper functions to start PB comms
    def runClient(self):
        f = pb.PBClientFactory()
        self.cport = reactor.connectTCP("127.0.0.1", self.port, f)
        d = f.getRootObject()
        d.addCallback(self.clientConnected)
        if weHaveAnOldTwisted():
            reactor.iterate()
        return d
        #.addCallbacks(self.connected, self.notConnected)
        # self.id = reactor.callLater(10, self.timeOut)

    def clientConnected(self, perspective):
        self.perspective = perspective
        self._dDisconnect = defer.Deferred()
        perspective.notifyOnDisconnect(
            lambda r: self._dDisconnect.callback(None))

    def stopClient(self):
        self.cport.disconnect()
        return self._dDisconnect

    def runServer(self):
        factory = pb.PBServerFactory(TestRoot())
        factory.unsafeTracebacks = 1
        self.sport = reactor.listenTCP(0, factory, interface="127.0.0.1")
        self.port = self.sport.getHost().port

    def stopServer(self):
        d = self.sport.stopListening()
        return d

    # actual tests
    implements(flavors.IStateListener)
    
    def customStateSet(self, state, key, value):
        self.changes.append(('set', state, key, value))

    def customStateAppend(self, state, key, value):
        self.changes.append(('append', state, key, value))

    def customStateRemove(self, state, key, value):
        self.changes.append(('remove', state, key, value))

    # listener tests
    def testStateSetListener(self):
        # start everything and get the state
        d = self.runClient()
        d.addCallback(lambda _: self.perspective.callRemote('getState'))

        # ask server to set the name
        def add_listener_and_set_name(state):
            d.state = state # monkeypatch
            state.addListener(self,
                              set=self.customStateSet,
                              append=self.customStateAppend,
                              remove=self.customStateRemove)
            return self.perspective.callRemote('setStateName', 'robin')

        def check_results(_):
            c = self.changes.pop()
            self.failUnlessEqual(c, ('set', d.state, 'name', 'robin'))
            return self.stopClient()

        d.addCallback(add_listener_and_set_name)
        d.addCallback(check_results)
        if weHaveAnOldTwisted(): #T1.3
            return unittest.deferredResult(d)
        else:
            return d

    def testStateAppendRemoveListener(self):
        # start everything and get the state
        d = self.runClient()
        d.addCallback(lambda _: self.perspective.callRemote('getState'))

        def add_listener_and_bear_child(state):
            d.state = state # monkeypatch
            # here test the positional-arguments code
            state.addListener(self,
                              None,
                              self.customStateAppend,
                              self.customStateRemove)
            return self.perspective.callRemote('bearChild', 'robin')

        def check_append_results_and_adopt_kid(_):
            c = self.changes.pop()
            self.failUnlessEqual(c, ('append', d.state, 'children', 'robin'))
            return self.perspective.callRemote('haveAdopted', 'robin')

        def check_remove_results_and_bear_child(_):
            c = self.changes.pop()
            self.failUnlessEqual(c, ('remove', d.state, 'children', 'robin'))
            return self.perspective.callRemote('bearChild', 'batman')

        def check_append_results_and_stop(_):
            c = self.changes.pop()
            self.failUnlessEqual(c, ('append', d.state, 'children', 'batman'))
            return self.stopClient()

        d.addCallback(add_listener_and_bear_child)
        d.addCallback(check_append_results_and_adopt_kid)
        d.addCallback(check_remove_results_and_bear_child)
        d.addCallback(check_append_results_and_stop)
        if weHaveAnOldTwisted(): #T1.3
            return unittest.deferredResult(d)
        else:
            return d


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
