# -*- Mode: Python; test-case-name: flumotion.test.test_manager_manager -*-
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

import os

from twisted.spread import pb
from twisted.internet import reactor, defer

from flumotion.common.planet import moods

from flumotion.manager import component, manager
from flumotion.common import log, planet, interfaces
from flumotion.common import setup

class FakeComponentAvatar(log.Loggable):
    ### since we fake out componentavatar, eaters need to be specified fully
    ### for the tests, ie sourceComponentName:feedName
    def __init__(self, name='fake', eaters=[], port=-1, listen_host='127.0.0.1'):
        self.name = name
        self.eaters = eaters
        self.port = port
        self.listen_host = listen_host
        
    def getFeeders(self):
        return [self.name + ':default']

    def getFeedPort(self, feedName):
        return self.port

    def getEaters(self):
        return self.eaters
    
    def getClientAddress(self):
        return self.listen_host

    def getListenPort(self, *args):
        return self.port
    
    def getName(self):
        return self.name

    def cleanup(self):
        pass

class TestComponentMapper(unittest.TestCase):
    def setUp(self):
        self._mappers = {}
        self.heaven = component.ComponentHeaven(manager.Vishnu())

    def testOneComponent(self):
        # create state and initial mapper and store it
        state = planet.ManagerComponentState()
        mapper = manager.ComponentMapper()

        m = mapper
        m.state = state

        # insert a state -> mapper ref
        self._mappers[state] = m

        # starting component with state gets us avatarId; lookup mapper
        id = '/adam/cain'
        m = self._mappers[state]
        self.assertEquals(m, mapper)
        
        m.id = id
        # insert a id -> mapper ref
        self._mappers[id] = m

        # verify we can do state -> id and other way around
        m = self._mappers[state]
        self.assertEquals(m.state, state)
        self.assertEquals(m.id, id)

        m = self._mappers[id]
        self.assertEquals(m.state, state)
        self.assertEquals(m.id, id)

        # a componentAvatar gets created with this avatarId
        # lookup mapper and add
        avatar = component.ComponentAvatar(self.heaven, id)
        m = self._mappers[id]
        m.avatar = avatar
        # insert an avatar -> mapper ref
        self._mappers[avatar] = m
 
        # verify we can do avatar -> (state, id) and other way
        m = self._mappers[avatar]
        self.assertEquals(m.state, state)
        self.assertEquals(m.id, id)

        m = self._mappers[state]
        self.assertEquals(m.avatar, avatar)
        self.assertEquals(m.id, id)

        m = self._mappers[id]
        self.assertEquals(m.state, state)
        self.assertEquals(m.avatar, avatar)

        # component avatar logs out, clean up id and avatar
        m = self._mappers[avatar]
        del self._mappers[m.id]
        del self._mappers[m.avatar]
        m.id = None
        m.avatar = None

        # verify that the keys are gone, and that the mapper on state
        # only has state left
        self.failIf(id in self._mappers.keys())
        self.failIf(avatar in self._mappers.keys())
        self.failUnless(state in self._mappers.keys())
        m = self._mappers[state]
        self.failIf(m.id)
        self.failIf(m.avatar)
        self.assertEquals(m.state, state)
        
class TestComponentHeaven(unittest.TestCase):
    def setUp(self):
        self.heaven = component.ComponentHeaven(manager.Vishnu())

    def testCreateAvatar(self):
        p = self.heaven.createAvatar('foo-bar-baz')
        assert isinstance(p, component.ComponentAvatar)

        #self.assertRaises(AssertionError,
        #                  self.heaven.createAvatar, 'does-not-exist')
        # make sure callbacks get cancelled
        # we moved heartbeat checks to attached
        # p.cleanup()

    def testComponentIsLocal(self):
        a = FakeComponentAvatar()
        self.heaven.avatars['test'] = a
        assert self.heaven._componentIsLocal(a)
        
    def testGetComponent(self):
        a = self.heaven.createAvatar('prod')
        assert self.heaven.getComponent('prod') == a
        a.cleanup()

    def testHasComponent(self):
        a = self.heaven.createAvatar('prod')
        assert self.heaven.hasComponent('prod')
        self.heaven.removeComponent(a)
        assert not self.heaven.hasComponent('prod')
        self.assertRaises(KeyError, self.heaven.removeComponent, a)
        a.cleanup()
        
    def testRemoveComponent(self):
        assert not self.heaven.hasComponent('fake')
        a = FakeComponentAvatar('fake')
        self.assertRaises(KeyError, self.heaven.removeComponent, a)
        self.heaven.avatars['fake'] = a
        assert self.heaven.hasComponent('fake')
        self.heaven.removeComponent(a)
        assert not self.heaven.hasComponent('fake')
        self.assertRaises(KeyError, self.heaven.removeComponent, a)

    def testComponentEatersEmpty(self):
        a = FakeComponentAvatar('fake')
        self.heaven.avatars['fake'] = a
        assert self.heaven._getComponentEatersData(a) == []
        
    def testComponentsEaters(self):
        a = FakeComponentAvatar('foo', ['bar:default', 'baz:default'])
        self.heaven.avatars['foo'] = a
        a2 = FakeComponentAvatar('bar', port=1000, listen_host='bar-host')
        self.heaven.avatars['bar'] = a2
        a3 = FakeComponentAvatar('baz', port=1001, listen_host='baz-host')
        self.heaven.avatars['baz'] = a3

        self.heaven._feederSet.addFeeders(a2)
        self.heaven._feederSet.addFeeders(a3)
        
        eaters = self.heaven._getComponentEatersData(a)
        assert len(eaters) == 2
        assert ('bar:default', 'bar-host', 1000) in eaters
        assert ('baz:default', 'baz-host', 1001) in eaters        

class FakeTransport:
    def getPeer(self):
        from twisted.internet.address import IPv4Address
        return IPv4Address('TCP', 'nullhost', 1)

class FakeBroker:
    def __init__(self):
        self.transport = FakeTransport()

class FakeMind(log.Loggable):
    def __init__(self, testcase):
        self.broker = FakeBroker()
        self.testcase = testcase

    def callRemote(self, name, *args, **kwargs):
        #print "callRemote(%s, %r, %r)" % (name, args, kwargs)
        method = "remote_" + name
        if hasattr(self, method):
            m = getattr(self, method)
            try:
                result = m(*args, **kwargs)
                return defer.succeed(result)
            except:
                return defer.fail()
        else:
            raise AttributeError('no method %s on self %r' % (name, self))

class FakeWorkerMind(FakeMind):

    logCategory = 'fakeworkermind'
    
    def __init__(self, testcase, avatarId):
        FakeMind.__init__(self, testcase)
        self.avatarId = avatarId

    def remote_start(self, avatarId, type, config):
        self.debug('remote_start(%s)' % avatarId)
        avatar = self.testcase._loginComponent(self.avatarId,
            avatarId, type, config)
        # need to return the avatarId for comparison
        return avatarId

class FakeComponentMind(FakeMind):

    logCategory = 'fakecomponentmind'

    def __init__(self, testcase, workerName, avatarId, type, config):
        FakeMind.__init__(self, testcase)

        state = planet.ManagerJobState()
        state._dict = {
            'type': type, 'pid': 1, 'mood': moods.waking.value,
            'ip': '0.0.0.0', 'workerName': workerName, 'message': None, 
            'feederNames': [], 'eaterNames': [] }
        self.state = state

    def remote_getState(self):
        self.debug('remote_getState: returning %r' % self.state)
        return self.state

    def remote_start(self, eatersData, feedersData):
        self.debug('remote_start(%r, %r)' % (eatersData, feedersData))
        self.testcase.failUnless(hasattr(self, 'state'))
        self.testcase.failUnless(hasattr(self.state, 'observe_set'))
        
        self.state.observe_set('mood', moods.happy.value)
        # need to return a list of (feedName, host, port) tuples
        return []
    
class TestVishnu(unittest.TestCase):
    def setUp(self):
        # load registry
        from flumotion.common.registry import registry
        registry.verify()

        self.vishnu = manager.Vishnu(unsafeTracebacks=1)
        self._workers = {}    # id -> avatar
        self._components = {} # id -> avatar

    # helper functions
    def _loginWorker(self, avatarId):
        # create a worker and log it in
        # return the avatar

        # log in a worker
        mind = FakeWorkerMind(self, avatarId)

        tuple = self.vishnu.dispatcher.requestAvatar(avatarId, mind,
            pb.IPerspective, interfaces.IWorkerMedium)

        avatar = tuple[1]

        # hack for cleanup
        avatar._tuple = tuple
        avatar._mind = mind
        avatar._avatarId = avatarId

        # trigger attached
        self.runReactor(1)

        self._workers[avatarId] = avatar
        return avatar

    def _loginComponent(self, workerName, avatarId, type, config):
        # create a component and log it in
        # return the avatar

        mind = FakeComponentMind(self, workerName, avatarId, type, config)

        tuple = self.vishnu.dispatcher.requestAvatar(avatarId, mind,
            pb.IPerspective, interfaces.IComponentMedium)

        avatar = tuple[1]

        # hack for cleanup
        avatar._tuple = tuple
        avatar._mind = mind
        avatar._avatarId = avatarId

        # trigger attached
        self.runReactor(1)

        self._components[avatarId] = avatar
        return avatar

    def _logoutAvatar(self, avatar):
        # log out avatar
        logout = avatar._tuple[2]
        mind = avatar._mind
        avatarId = avatar._avatarId

        logout(avatar, mind, avatarId)
        
        # trigger detached
        self.runReactor(1)

    def testWorker(self):
        names = self.vishnu.workerHeaven.state.get('names')
        self.failUnlessEqual(len(names), 0)

        avatar = self._loginWorker('worker')

        # check
        names = self.vishnu.workerHeaven.state.get('names')
        self.failUnlessEqual(len(names), 1)
        self.failUnless('worker' in names)

        self._logoutAvatar(avatar)

        # check
        names = self.vishnu.workerHeaven.state.get('names')
        self.failUnlessEqual(len(names), 0)

    def testLoadConfiguration(self):
        __thisdir = os.path.dirname(os.path.abspath(__file__))
        file = os.path.join(__thisdir, 'test.xml')
        
        self.vishnu.loadConfiguration(file)
        s = self.vishnu.state
        
        l = s.get('flows')
        self.failUnless(l)
        f = l[0]
        self.failUnlessEqual(f.get('name'), 'test')
        
        l = f.get('components')
        self.failUnless(l)

        self.vishnu.loadConfiguration(file)

    def testConfigComponentWorker(self):
        mappers = self.vishnu._componentMappers

        # test loading of a config, logging in the component and worker,
        # and their cleanup
        __thisdir = os.path.dirname(os.path.abspath(__file__))
        file = os.path.join(__thisdir, 'test.xml')
        
        self.vishnu.loadConfiguration(file)

        # verify component mapper
        # 3 component states + avatarId's gotten from the config
        self.assertEqual(len(mappers.keys()), 6)

        # log in a worker and verify components get started
        avatar = self._loginWorker('worker')
        self.runReactor(100)
        self.failUnlessEqual(len(self._workers), 1)
        self.failUnlessEqual(len(self._components), 2)
        
        self.failUnless('producer-video-test' in self._components.keys())
        self.failUnless('converter-ogg-theora' in self._components.keys())

        # verify mapper
        # 1 component with state and id
        # 2 components with state, avatar, id, and jobstate
        self.assertEqual(len(mappers.keys()), 10)

        id = 'producer-video-test'
        avatar = self._components[id]
        self.failUnless(id in mappers.keys())
        self.failUnless(avatar in mappers.keys())

        m = mappers[id]

        self.assertEqual(m.id, id)
        self.assertEqual(m.avatar, avatar)
        self.failUnless(m.state)
        self.failUnless(m.jobState)

        state = m.state
        self.assertEqual(state.get('mood'), moods.happy.value)
 
        # verify the component avatars
        self.failUnless(avatar.jobState)
        self.failUnless(avatar.componentState)

        # log out the producer and verify the mapper
        id = 'producer-video-test'
        avatar = self._components[id]
        m = mappers[avatar]

        self._logoutAvatar(avatar)

        #import pprint
        #pprint.pprint(mappers.keys())
        self.assertEqual(len(mappers.keys()), 8)
        self.failUnless(id in mappers.keys())
        self.assertEqual(m.id, id)
        self.failIf(avatar in mappers.keys())
        
        self.assertEqual(m.avatar, None)
        self.failUnless(m.state)
        state = m.state
        self.assertEqual(state.get('mood'), moods.sleeping.value,
            'mood is %s instead of sleeping' % moods.get(state.get('mood')))

        # verify avatar state
        self.failIf(avatar.jobState)
        self.failIf(avatar.componentState)

        # log out the converter and verify
        id = 'converter-ogg-theora'
        m = mappers[id]
        avatar = self._components[id]
        self._logoutAvatar(avatar)

        # verify mapper
        self.assertEqual(len(mappers.keys()), 6)
        self.failUnless(id in mappers.keys())
        self.assertEqual(m.id, id)
        self.failIf(avatar in mappers.keys())
        
        self.assertEqual(m.avatar, None)
        self.failUnless(m.state)
        state = m.state
        self.assertEqual(state.get('mood'), moods.sleeping.value,
            'mood is %s instead of sleeping' % moods.get(state.get('mood')))

        # verify avatar state
        self.failIf(avatar.jobState)
        self.failIf(avatar.componentState)
