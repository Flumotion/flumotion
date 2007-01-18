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

import common
import testclasses

from twisted.trial import unittest

from twisted.internet import reactor, defer
from twisted.spread import pb

from flumotion.twisted import flavors
from flumotion.twisted.compat import implements
from flumotion.common import componentui

from flumotion.twisted.defer import defer_generator_method

import twisted.copyright #T1.3
#T1.3
def weHaveAnOldTwisted():
    return twisted.copyright.version[0] < '2'

class FakeObject: pass

class FakeAdmin(testclasses.TestAdmin):
    pass

class FakeWorker(testclasses.TestWorker):
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

class TestRoot(testclasses.TestManagerRoot):
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

class TestStateSet(unittest.TestCase):
    def setUp(self):
        self.changes = []
        
        self._m = testclasses.TestManager()
        port = self._m.run(TestRoot)
        self.admin = FakeAdmin()
        d = self.admin.run(port)
        if weHaveAnOldTwisted():
            unittest.deferredResult(d)
        else:
            yield d
        self.worker = FakeWorker()
        d = self.worker.run(port)
        if weHaveAnOldTwisted():
            unittest.deferredResult(d)
        else:
            yield d
    setUp = defer_generator_method(setUp)

    def tearDown(self):
        if weHaveAnOldTwisted():
            unittest.deferredResult(self._m.stop())
            unittest.deferredResult(self.admin.stop())
            unittest.deferredResult(self.worker.stop())
        else:
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
        if weHaveAnOldTwisted():
            state = unittest.deferredResult(d)

            self.failUnless(state)
            self.failUnless(state.hasKey('name'))
            self.failUnless(state.hasKey('children'))

            self.failUnlessEqual(state.get('name'), 'lois')

            # change state by setting the name
            d = self.admin.remoteRoot.callRemote('workerSetName', 'clark')
            unittest.deferredResult(d)

            self.failUnlessEqual(state.get('name'), 'clark')
        else:
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
        if weHaveAnOldTwisted():
            state = unittest.deferredResult(d)
            self.failUnless(state)
            self.failUnless(state.hasKey('children'))

            # change state by adding children
            d = self.admin.remoteRoot.callRemote('workerBearChild', 'batman')
            unittest.deferredResult(d)

            self.failUnlessEqual(state.get('children'), ['batman', ])
        else:
            def workerGetStateCallback(state):
                self.failUnless(state)
                self.failUnless(state.hasKey('children'))

                d = self.admin.remoteRoot.callRemote('workerBearChild', 
                    'batman')
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

    if weHaveAnOldTwisted():
        testSimpleStateListener.skip = True

    # change state by appending children
    if weHaveAnOldTwisted():
        def testStateListener(self):
            self.reset()
            d = self.admin.remoteRoot.callRemote('workerGetState')
            state = unittest.deferredResult(d)

            self.listen(state)

            self.failUnless(state)
            self.failUnless(state.hasKey('children'))
            self.failIf(self.changes, self.changes)

            # change state by adding children
            d = self.admin.remoteRoot.callRemote('workerBearChild', 'batman')
            unittest.deferredResult(d)
            c = self.changes.pop()
            self.failUnlessEqual(c, ('append', state, 'children', 'batman'))
            # make sure this is the only change
            self.failIf(self.changes, self.changes)

            d = self.admin.remoteRoot.callRemote('workerBearChild', 'robin')
            unittest.deferredResult(d)
            c = self.changes.pop()
            self.failUnlessEqual(c, ('append', state, 'children', 'robin'))
            self.failIf(self.changes, self.changes)

            d = self.admin.remoteRoot.callRemote('workerHaveAdopted', 'batman')
            unittest.deferredResult(d)
            c = self.changes.pop()
            self.failUnlessEqual(c, ('remove', state, 'children', 'batman'))
            self.failIf(self.changes, self.changes)
            state.removeListener(self)
            del state
    else:
        def testStateListener(self):
            def getStateCallback(state):
                self.listen(state)
                self._state = state
                self.failUnless(state)
                self.failUnless(state.hasKey('children'))
                self.failIf(self.changes, self.changes)
                return self.admin.remoteRoot.callRemote('workerBearChild', 'batman')

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
                return self.admin.remoteRoot.callRemote('workerHaveAdopted', 'batman')

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
    if weHaveAnOldTwisted():
        def testStateListenerIntermediate(self):
            self.reset()
            # get the state
            d = self.admin.remoteRoot.callRemote('workerGetState')
            state = unittest.deferredResult(d)
            self.listen(state)

            self.failUnless(state)
            self.failUnless(state.hasKey('children'))
            self.failIf(self.changes, self.changes)

            # change state by adding children
            d = self.admin.remoteRoot.callRemote('workerBearChild', 'batman')
            unittest.deferredResult(d)
            c = self.changes.pop()
            self.failUnlessEqual(c, ('append', state, 'children', 'batman'))
            # make sure this is the only change
            self.failIf(self.changes, self.changes)
            self.assertEquals(len(state.get('children')), 1)

            state.removeListener(self)
            del state

            # get the state again
            d = self.admin.remoteRoot.callRemote('workerGetState')
            state = unittest.deferredResult(d)

            self.listen(state)
            self.assertEquals(len(state.get('children')), 1)

            d = self.admin.remoteRoot.callRemote('workerBearChild', 'robin')
            unittest.deferredResult(d)
            c = self.changes.pop()
            self.failUnlessEqual(c, ('append', state, 'children', 'robin'))
            self.failIf(self.changes, self.changes)

            d = self.admin.remoteRoot.callRemote('workerHaveAdopted', 'batman')
            unittest.deferredResult(d)
            c = self.changes.pop()
            self.failUnlessEqual(c, ('remove', state, 'children', 'batman'))
            self.failIf(self.changes, self.changes)
            state.removeListener(self)
            del state
    else:
        def testStateListenerIntermediate(self):
            def workerGetStateCallback(state):
                self.listen(state)
                self.failUnless(state)
                self.failUnless(state.hasKey('children'))
                self.failIf(self.changes, self.changes)
                self._state = state
                return self.admin.remoteRoot.callRemote('workerBearChild',
                    'batman')
                        
            def workerBearChildCallback(result):
                state = self._state
                del self._state
                self.failIf(self.changes == [])
                c = self.changes.pop()
                self.failUnlessEqual(c, ('append', state, 'children', 
                    'batman'))
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
                return self.admin.remoteRoot.callRemote('workerBearChild',
                    'robin')
                
            def workerBearChildAgainCallback(result):
                state = self._state
                self.failUnless(self.changes)
                c = self.changes.pop()
                self.failUnlessEqual(c, ('append', state, 
                    'children', 'robin'))
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
                        
    def testStateSaveReference(self):
        # show that we need to keep the state reference around for listener
        # to work
        self.reset()
        # get the state
        d = self.admin.remoteRoot.callRemote('workerGetState')
        if weHaveAnOldTwisted():
            state = unittest.deferredResult(d)

            self.listen(state)

            self.failUnless(state)
            self.failUnless(state.hasKey('children'))

            del state

            # change state by adding children
            d = self.admin.remoteRoot.callRemote('workerBearChild', 'batman')
            unittest.deferredResult(d)
            self.failIf(self.changes)
        else:
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

