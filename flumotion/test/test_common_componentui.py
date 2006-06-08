# -*- Mode: Python; test-case-name: flumotion.test.test_common_componentui -*-
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

from twisted.trial import unittest

from twisted.internet import reactor
from twisted.spread import pb

from flumotion.twisted import flavors
from flumotion.twisted.compat import implements
from flumotion.common import componentui

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
        unittest.deferredResult(d)
        self.worker = FakeWorker()
        d = self.worker.run(port)
        unittest.deferredResult(d)

    def tearDown(self):
        unittest.deferredResult(self._m.stop())
        unittest.deferredResult(self.admin.stop())
        unittest.deferredResult(self.worker.stop())

    def reset(self):
        self.changes = []
        
    def testStateSet(self):
        self.reset()
        # get the state
        d = self.admin.perspective.callRemote('workerGetState')
        state = unittest.deferredResult(d)

        self.failUnless(state)
        self.failUnless(state.hasKey('name'))
        self.failUnless(state.hasKey('children'))

        self.failUnlessEqual(state.get('name'), 'lois')

        # change state by setting the name
        d = self.admin.perspective.callRemote('workerSetName', 'clark')
        unittest.deferredResult(d)

        self.failUnlessEqual(state.get('name'), 'clark')

    def testStateAppend(self):
        # change state by appending children
        self.reset()
        # get the state
        d = self.admin.perspective.callRemote('workerGetState')
        state = unittest.deferredResult(d)

        self.failUnless(state)
        self.failUnless(state.hasKey('children'))

        # change state by adding children
        d = self.admin.perspective.callRemote('workerBearChild', 'batman')
        unittest.deferredResult(d)

        self.failUnlessEqual(state.get('children'), ['batman', ])

    # listener interface
    implements(flavors.IStateListener)
    
    def stateSet(self, state, key, value):
        self.changes.append(('set', state, key, value))

    def stateAppend(self, state, key, value):
        self.changes.append(('append', state, key, value))

    def stateRemove(self, state, key, value):
        self.changes.append(('remove', state, key, value))

    def testStateListener(self):
        # change state by appending children
        self.reset()
        # get the state
        d = self.admin.perspective.callRemote('workerGetState')
        state = unittest.deferredResult(d)

        state.addListener(self)

        self.failUnless(state)
        self.failUnless(state.hasKey('children'))
        self.failIf(self.changes, self.changes)

        # change state by adding children
        d = self.admin.perspective.callRemote('workerBearChild', 'batman')
        unittest.deferredResult(d)
        c = self.changes.pop()
        self.failUnlessEqual(c, ('append', state, 'children', 'batman'))
        # make sure this is the only change
        self.failIf(self.changes, self.changes)

        d = self.admin.perspective.callRemote('workerBearChild', 'robin')
        unittest.deferredResult(d)
        c = self.changes.pop()
        self.failUnlessEqual(c, ('append', state, 'children', 'robin'))
        self.failIf(self.changes, self.changes)

        d = self.admin.perspective.callRemote('workerHaveAdopted', 'batman')
        unittest.deferredResult(d)
        c = self.changes.pop()
        self.failUnlessEqual(c, ('remove', state, 'children', 'batman'))
        self.failIf(self.changes, self.changes)
        state.removeListener(self)
        del state

    def testStateListenerIntermediate(self):
        # change state by appending children
        # verify if we have the right number of items proxied,
        # ie the manager reference doesn't do something weird
        self.reset()
        # get the state
        d = self.admin.perspective.callRemote('workerGetState')
        state = unittest.deferredResult(d)

        state.addListener(self)

        self.failUnless(state)
        self.failUnless(state.hasKey('children'))
        self.failIf(self.changes, self.changes)

        # change state by adding children
        d = self.admin.perspective.callRemote('workerBearChild', 'batman')
        unittest.deferredResult(d)
        c = self.changes.pop()
        self.failUnlessEqual(c, ('append', state, 'children', 'batman'))
        # make sure this is the only change
        self.failIf(self.changes, self.changes)
        self.assertEquals(len(state.get('children')), 1)

        state.removeListener(self)
        del state

        # get the state again
        d = self.admin.perspective.callRemote('workerGetState')
        state = unittest.deferredResult(d)

        state.addListener(self)
        self.assertEquals(len(state.get('children')), 1)

        d = self.admin.perspective.callRemote('workerBearChild', 'robin')
        unittest.deferredResult(d)
        c = self.changes.pop()
        self.failUnlessEqual(c, ('append', state, 'children', 'robin'))
        self.failIf(self.changes, self.changes)

        d = self.admin.perspective.callRemote('workerHaveAdopted', 'batman')
        unittest.deferredResult(d)
        c = self.changes.pop()
        self.failUnlessEqual(c, ('remove', state, 'children', 'batman'))
        self.failIf(self.changes, self.changes)
        state.removeListener(self)
        del state

    def testStateSaveReference(self):
        # show that we need to keep the state reference around for listener
        # to work
        self.reset()
        # get the state
        d = self.admin.perspective.callRemote('workerGetState')
        state = unittest.deferredResult(d)

        state.addListener(self)

        self.failUnless(state)
        self.failUnless(state.hasKey('children'))

        del state

        # change state by adding children
        d = self.admin.perspective.callRemote('workerBearChild', 'batman')
        unittest.deferredResult(d)
        self.failIf(self.changes)

