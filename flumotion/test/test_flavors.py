# -*- Mode: Python; test-case-name: flumotion.test.test_flavors -*-
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

from twisted.internet import reactor, defer
from twisted.spread import pb
from zope.interface import implements

from flumotion.common import testsuite
from flumotion.twisted import flavors


class TestStateCacheable(flavors.StateCacheable):
    pass


class TestStateRemoteCache(flavors.StateRemoteCache):
    pass

pb.setUnjellyableForClass(TestStateCacheable, TestStateRemoteCache)


class FakeObject:
    pass


class FakeListener:
    # listener interface
    implements(flavors.IStateListener)

    def stateSet(self, state, key, value):
        pass

    def stateAppend(self, state, key, value):
        pass

    def stateRemove(self, state, key, value):
        pass


class TestRoot(testsuite.TestManagerRoot):

    def remote_getState(self):
        self.state = TestStateCacheable()
        self.state.addKey('name', 'lois')
        self.state.addListKey('children')
        self.state.addDictKey('nationalities')
        return self.state

    def remote_setStateName(self, name):
        return self.state.set('name', name)

    def remote_haggis(self):
        return self.state.setitem('nationalities',
                                  'mary queen of scots', 'scotland')

    def remote_emigrate(self):
        return self.state.setitem('nationalities',
                                  'mary queen of scots', 'norway')

    def remote_coup(self):
        return self.state.delitem('nationalities',
                                     'mary queen of scots')

    def remote_bearChild(self, name):
        return self.state.append('children', name)

    def remote_haveAdopted(self, name):
        return self.state.remove('children', name)


class StateTest(testsuite.TestCase):

    def setUp(self):
        self.changes = []
        self.runServer()

    def tearDown(self):
        return self.stopServer()

    def runClient(self):
        f = pb.PBClientFactory()
        self.cport = reactor.connectTCP("127.0.0.1", self.port, f)
        d = f.getRootObject()
        d.addCallback(self.clientConnected)
        return d

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


class TestStateSet(StateTest):

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
        return d

    def testStateWrongListener(self):
        # start everything
        d = self.runClient()
        d.addCallback(lambda _: self.perspective.callRemote('getState'))

        def got_state_and_stop(state):
            self.assertRaises(Exception, state.addListener, FakeObject())
            self.assertRaises(KeyError, state.removeListener, FakeObject())
            return self.stopClient()

        d.addCallback(got_state_and_stop)
        return d

    def listen(self, state):

        def event(type):
            return lambda *x: self.changes.append((type, ) + x)
        state.addListener(self, set_=event('set'), append=event('append'),
                          remove=event('remove'), setitem=event('setitem'),
                          delitem=event('delitem'))

    # listener tests

    def testStateSetListener(self):
        # start everything and get the state
        d = self.runClient()
        d.addCallback(lambda _: self.perspective.callRemote('getState'))

        # ask server to set the name

        def add_listener_and_set_name(state):
            d.state = state # monkeypatch
            self.listen(state)
            return self.perspective.callRemote('setStateName', 'robin')

        def check_results(_):
            c = self.changes.pop()
            self.failUnlessEqual(c, ('set', d.state, 'name', 'robin'))
            return self.stopClient()

        d.addCallback(add_listener_and_set_name)
        d.addCallback(check_results)
        return d

    def testStateAppendRemoveListener(self):
        # start everything and get the state
        d = self.runClient()
        d.addCallback(lambda _: self.perspective.callRemote('getState'))

        def add_listener_and_bear_child(state):
            d.state = state # monkeypatch
            self.listen(state)
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
        return d

    def testStateDictListener(self):
        # start everything and get the state
        d = self.runClient()
        d.addCallback(lambda _: self.perspective.callRemote('getState'))

        def add_listener_and_haggis(state):
            d.state = state # monkeypatch
            self.listen(state)
            return self.perspective.callRemote('haggis')

        def check_set_results_and_emigrate(_):
            c = self.changes.pop()
            self.failUnlessEqual(c, ('setitem', d.state, 'nationalities',
                                     'mary queen of scots', 'scotland'))
            return self.perspective.callRemote('emigrate')

        def check_set_results_and_coup_de_etat(_):
            c = self.changes.pop()
            self.failUnlessEqual(c, ('setitem', d.state, 'nationalities',
                                     'mary queen of scots', 'norway'))
            return self.perspective.callRemote('coup')

        def check_remove_results_and_stop(_):
            c = self.changes.pop()
            self.failUnlessEqual(c, ('delitem', d.state,
                                     'nationalities',
                                     'mary queen of scots', 'norway'))
            return self.stopClient()

        d.addCallback(add_listener_and_haggis)
        d.addCallback(check_set_results_and_emigrate)
        d.addCallback(check_set_results_and_coup_de_etat)
        d.addCallback(check_remove_results_and_stop)
        return d


class TestFullListener(StateTest):

    def testStateSetListener(self):
        # start everything and get the state
        d = self.runClient()
        d.addCallback(lambda _: self.perspective.callRemote('getState'))

        def customStateSet(state, key, value):
            self.changes.append(('set', state, key, value))

        # ask server to set the name

        def add_listener_and_set_name(state):
            d.state = state # monkeypatch
            state.addListener(self, set_=customStateSet)
            return self.perspective.callRemote('setStateName', 'robin')

        def check_results(_):
            c = self.changes.pop()
            self.failUnlessEqual(c, ('set', d.state, 'name', 'robin'))
            return self.stopClient()

        d.addCallback(add_listener_and_set_name)
        d.addCallback(check_results)
        return d

    def testStateAppendRemoveListener(self):
        # start everything and get the state
        d = self.runClient()
        d.addCallback(lambda _: self.perspective.callRemote('getState'))

        def customStateAppend(state, key, value):
            self.changes.append(('append', state, key, value))

        def customStateRemove(state, key, value):
            self.changes.append(('remove', state, key, value))

        def add_listener_and_bear_child(state):
            d.state = state # monkeypatch
            # here test the positional-arguments code
            state.addListener(self, append=customStateAppend,
                              remove=customStateRemove)
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
        return d

    def testInvalidate(self):
        calls = []

        def check_invalidation(state):

            def invalidate(obj):
                calls.append(('invalidate', obj))

            def unused(*args):
                assert False, 'should not be reached'
            self.assertEquals(calls, [])
            state.addListener(1, invalidate=invalidate)
            state.invalidate()
            # basic invalidation
            self.assertEquals(calls, [('invalidate', state)])

            # connecting after invalidation
            state.addListener(2, invalidate=invalidate)
            self.assertEquals(calls, [('invalidate', state),
                                      ('invalidate', state)])

            state.addListener(3, set_=unused)
            self.assertEquals(calls, [('invalidate', state),
                                      ('invalidate', state)])

            return self.stopClient()

        d = self.runClient()
        d.addCallback(lambda _: self.perspective.callRemote('getState'))
        d.addCallback(check_invalidation)
        return d


class TestState(testsuite.TestCase):

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

    def testStateDictAppendRemove(self):
        c = flavors.StateCacheable()

        c.addDictKey('adict')

        c.setitem('adict', 'akey', 'avalue')
        self.assertEquals(c.get('adict'), {'akey': 'avalue'})
        c.setitem('adict', 'akey', 'bvalue')
        self.assertEquals(c.get('adict'), {'akey': 'bvalue'})

        c.delitem('adict', 'akey')
        self.assertEquals(c.get('adict'), {})
        self.assertRaises(KeyError, c.delitem, 'randomdictkey', 'value')
        self.assertRaises(KeyError, c.delitem, 'adict', 'akey')
