# -*- Mode: Python; test-case-name: flumotion.test.test_common_componentui -*-
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

from flumotion.common import componentui
from flumotion.common import testsuite
from flumotion.twisted.defer import defer_generator_method

attr = testsuite.attr


class FakeObject:
    pass


class FakeAdmin(testsuite.TestAdmin):
    pass


class FakeWorker(testsuite.TestWorker):

    def remote_getState(self):
        if not hasattr(self, 'state'):
            self.state = componentui.WorkerComponentUIState()
            self.state.addKey('name', 'lois')
            self.state.addListKey('children')
        return self.state

    def remote_setName(self, name):
        self.state.set('name', name)

    def remote_bearChild(self, name):
        self.state.append('children', name)

    def remote_haveAdopted(self, name):
        self.state.remove('children', name)


class TestRoot(testsuite.TestManagerRoot):

    def remote_workerGetState(self):
        d = self.workerReference.callRemote('getState')
        d.addCallback(self._workerGotState)
        return d

    def _workerGotState(self, result):
        # keeping a reference around makes sure that the manager reference
        # stays around when we delete the admin reference
        # this helps us bring out bugs in the ManagerUIState object
        # where keys got doubly appended
        self.managerState = result
        return result

    def remote_workerSetName(self, name):
        return self.workerReference.callRemote('setName', name)

    def remote_workerBearChild(self, name):
        return self.workerReference.callRemote('bearChild', name)

    def remote_workerHaveAdopted(self, name):
        return self.workerReference.callRemote('haveAdopted', name)


class TestStateSet(testsuite.TestCase):

    def setUp(self):
        self.changes = []

        self._m = testsuite.TestManager()
        port = self._m.run(TestRoot)
        self.admin = FakeAdmin()
        d = self.admin.run(port)
        yield d
        self.worker = FakeWorker()
        d = self.worker.run(port)
        yield d
    setUp = defer_generator_method(setUp)

    def tearDown(self):
        yield self._m.stop()
        yield self.admin.stop()
        yield self.worker.stop()
    tearDown = defer_generator_method(tearDown)

    def reset(self):
        self.changes = []

    def testStateSet(self):
        self.reset()
        # get the state
        d = self.admin.remoteRoot.callRemote('workerGetState')

        def workerGetStateCallback(state):
            self.failUnless(state)
            self.failUnless(state.hasKey('name'))
            self.failUnless(state.hasKey('children'))
            self.failUnlessEqual(state.get('name'), 'lois')

            d = self.admin.remoteRoot.callRemote('workerSetName', 'clark')

            def workerSetNameCallback(result):
                self.failUnlessEqual(state.get('name'), 'clark')
            d.addCallback(workerSetNameCallback)
            return d
        d.addCallback(workerGetStateCallback)
        return d

    def testStateAppend(self):
        # change state by appending children
        self.reset()
        # get the state
        d = self.admin.remoteRoot.callRemote('workerGetState')

        def workerGetStateCallback(state):
            self.failUnless(state)
            self.failUnless(state.hasKey('children'))

            d = self.admin.remoteRoot.callRemote('workerBearChild', 'batman')

            def workerBearChildCallback(result):
                self.failUnlessEqual(state.get('children'), ['batman', ])
            d.addCallback(workerBearChildCallback)
            return d
        d.addCallback(workerGetStateCallback)
        return d

    def listen(self, state):

        def event(type):
            return lambda o, k, v: self.changes.append((type, o, k, v))
        state.addListener(self, event('set'), event('append'),
                          event('remove'))

    # This is a simple test to show that explicitly del'ing the
    # state causes a decache further up and so no changes to be
    # sent from the Cachable object.  This is only for Twisted 2.x

    def testSimpleStateListener(self):

        def getStateCallback(state):
            self.listen(state)
            self._state = state
            return self.admin.remoteRoot.callRemote('workerBearChild',
                                                     'batman')

        def workerBearChildCallback(res):
            state = self._state
            del self._state
            self.failUnless(self.changes)
            c = self.changes.pop()
            self.failUnlessEqual(c, ('append', state, 'children', 'batman'))
            self.failIf(self.changes, self.changes)
            state.removeListener(self)
            del state

        self.reset()
        d = self.admin.remoteRoot.callRemote('workerGetState')
        d.addCallback(getStateCallback)
        d.addCallback(workerBearChildCallback)
        return d

    @attr('slow')
    def testStateListener(self):

        def getStateCallback(state):
            self.listen(state)
            self._state = state
            self.failUnless(state)
            self.failUnless(state.hasKey('children'))
            self.failIf(self.changes, self.changes)
            return self.admin.remoteRoot.callRemote(
                'workerBearChild', 'batman')

        def workerBearChildCallback(res):
            state = self._state
            self.failUnless(self.changes)
            c = self.changes.pop()
            self.failUnlessEqual(c, ('append', state, 'children', 'batman'))
            # make sure this is the only change
            self.failIf(self.changes, self.changes)
            return self.admin.remoteRoot.callRemote('workerBearChild', 'robin')

        def workerBearChildRobinCallback(res):
            state = self._state
            self.failUnless(self.changes)
            c = self.changes.pop()
            self.failUnlessEqual(c, ('append', state, 'children', 'robin'))
            self.failIf(self.changes, self.changes)
            return self.admin.remoteRoot.callRemote(
                'workerHaveAdopted', 'batman')

        def workerHaveAdoptedCallback(res):
            state = self._state
            del self._state
            self.failUnless(self.changes)
            c = self.changes.pop()
            self.failUnlessEqual(c, ('remove', state, 'children', 'batman'))
            self.failIf(self.changes, self.changes)
            state.removeListener(self)
            del state

        self.reset()
        d = self.admin.remoteRoot.callRemote('workerGetState')
        d.addCallback(getStateCallback)
        d.addCallback(workerBearChildCallback)
        d.addCallback(workerBearChildRobinCallback)
        d.addCallback(workerHaveAdoptedCallback)
        return d

    # change state by appending children
    # verify if we have the right number of items proxied,
    # ie the manager reference doesn't do something weird

    @attr('slow')
    def testStateListenerIntermediate(self):

        def workerGetStateCallback(state):
            self.listen(state)
            self.failUnless(state)
            self.failUnless(state.hasKey('children'))
            self.failIf(self.changes, self.changes)
            self._state = state
            return self.admin.remoteRoot.callRemote(
                'workerBearChild', 'batman')

        def workerBearChildCallback(result):
            state = self._state
            del self._state
            self.failIf(self.changes == [])
            c = self.changes.pop()
            self.failUnlessEqual(c, ('append', state, 'children', 'batman'))
            # make sure this is the only change
            self.failIf(self.changes, self.changes)
            self.assertEquals(len(state.get('children')), 1)
            state.removeListener(self)
            del state
            return self.admin.remoteRoot.callRemote('workerGetState')

        def workerGetStateAgainCallback(state):
            self.listen(state)
            self.assertEquals(len(state.get('children')), 1)
            self._state = state
            return self.admin.remoteRoot.callRemote('workerBearChild', 'robin')

        def workerBearChildAgainCallback(result):
            state = self._state
            self.failUnless(self.changes)
            c = self.changes.pop()
            self.failUnlessEqual(c, ('append', state, 'children', 'robin'))
            self.failIf(self.changes, self.changes)
            del state
            return self.admin.remoteRoot.callRemote(
                'workerHaveAdopted', 'batman')

        def workerHaveAdoptedCallback(result):
            state = self._state
            del self._state
            self.failUnless(self.changes)
            c = self.changes.pop()
            self.failUnlessEqual(c,
                ('remove', state, 'children', 'batman'))
            self.failIf(self.changes, self.changes)
            state.removeListener(self)
            del state

        # get the state again
        d = self.admin.remoteRoot.callRemote('workerGetState')
        d.addCallback(workerGetStateCallback)
        d.addCallback(workerBearChildCallback)
        d.addCallback(workerGetStateAgainCallback)
        d.addCallback(workerBearChildAgainCallback)
        d.addCallback(workerHaveAdoptedCallback)
        return d

    @attr('slow')
    def testStateSaveReference(self):
        # show that we need to keep the state reference around for listener
        # to work
        self.reset()
        # get the state
        d = self.admin.remoteRoot.callRemote('workerGetState')

        def workerGetStateCallback(state):
            self.listen(state)
            self.failUnless(state)
            self.failUnless(state.hasKey('children'))

            del state

            # change state by adding children
            d = self.admin.remoteRoot.callRemote('workerBearChild', 'batman')

            def workerBearChildCallback(res):
                self.failIf(self.changes)
            d.addCallback(workerBearChildCallback)
            return d
        d.addCallback(workerGetStateCallback)
        return d
