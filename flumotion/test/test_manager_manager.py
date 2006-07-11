# -*- Mode: Python; test-case-name: flumotion.test.test_manager_manager -*-
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

import os
import exceptions

from twisted.spread import pb
from twisted.internet import reactor, defer

from flumotion.common.planet import moods

from flumotion.manager import component, manager
from flumotion.common import log, planet, interfaces, common
from flumotion.common import setup
from flumotion.twisted import flavors
from flumotion.twisted.compat import implements

import twisted.copyright #T1.3
#T1.3
def weHaveAnOldTwisted():
    return twisted.copyright.version[0] < '2'

class MyListener(log.Loggable):
    # a helper object that you can get deferreds from that fire when
    # a certain state has a certain key set to a certain value
    implements(flavors.IStateListener)

    def __init__(self):
        self._setters = {} # (state, key, value) tuple -> list of deferred
        
    def notifyOnSet(self, state, key, value):
        self.debug("notify on state %r key %r set to value %r" % (
            state, key, value))
        
        if state.hasKey(key) and state.get(key) == value:
            self.debug("key already has the given value, firing")
            return defer.succeed(None)
            
        d = defer.Deferred()
        t = (state, key, value)
        if not t in self._setters.keys():
            self._setters[t] = []
        self._setters[t].append(d)
        self.debug("created notify deferred %r" % d)
        return d

    def stateSet(self, object, key, value):
        self.debug("%r key %r set to %r" % (object, key, value))
        
        t = (object, key, value)
        if t in self._setters.keys():
            list = self._setters[t]
            for d in list:
                self.debug("firing deferred %d" % d)
                d.callback(None)
            del self._setters[t]

    def stateAppend(self, object, key, value): pass
    def stateRemove(self, object, key, value): pass
    
class FakeComponentAvatar(log.Loggable):
    ### since we fake out componentavatar, eaters need to be specified fully
    ### for the tests, ie sourceComponentName:feedName
    def __init__(self, name='fake', parent='eve', eaters=[], port=-1,
                 listen_host='127.0.0.1'):
        self.name = name
        self.parent = parent
        self.avatarId = common.componentPath(name, parent)
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

    def getParentName(self):
        return self.parent

    def cleanup(self):
        pass

class TestComponentMapper(unittest.TestCase):
    def setUp(self):
        self._mappers = {}
        self.heaven = component.ComponentHeaven(manager.Vishnu('test'))

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
        avatar = component.ComponentAvatar(self.heaven, id, None)
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
        self.heaven = component.ComponentHeaven(manager.Vishnu('test'))

    def testCreateAvatar(self):
        p = self.heaven.createAvatar('foo-bar-baz', None)
        self.failUnless(isinstance(p, component.ComponentAvatar))

        #self.assertRaises(AssertionError,
        #                  self.heaven.createAvatar, 'does-not-exist')
        # make sure callbacks get cancelled
        # we moved heartbeat checks to attached
        # p.cleanup()

    def testComponentIsLocal(self):
        a = FakeComponentAvatar()
        self.heaven.avatars['test'] = a
        self.failUnless(self.heaven._componentIsLocal(a))

        
    def testGetComponent(self):
        a = self.heaven.createAvatar('prod', None)
        self.assertEqual(self.heaven.getAvatar('prod'), a)
        a.cleanup()

    def testHasComponent(self):
        a = self.heaven.createAvatar('prod', None)
        self.failUnless(self.heaven.hasAvatar('prod'))

        self.heaven.removeComponent(a)
        self.failIf(self.heaven.hasAvatar('prod'))
        self.assertRaises(KeyError, self.heaven.removeComponent, a)

        a.cleanup()

    def testRemoveComponent(self):
        self.failIf(self.heaven.hasAvatar('fake'))

        a = FakeComponentAvatar('fake')
        self.assertRaises(KeyError, self.heaven.removeComponent, a)
        self.failIf(self.heaven.hasAvatar(a.avatarId))

        self.heaven.avatars[a.avatarId] = a
        self.failUnless(self.heaven.hasAvatar(a.avatarId))

        self.heaven.removeComponent(a)
        self.failIf(self.heaven.hasAvatar(a.avatarId))
        self.assertRaises(KeyError, self.heaven.removeComponent, a)

    def testComponentEatersEmpty(self):
        a = FakeComponentAvatar('fake')
        self.heaven.avatars[a.avatarId] = a
        self.assertEquals(self.heaven._getComponentEatersData(a), [])
        
    def testComponentsEaters(self):
        a = FakeComponentAvatar(name='foo',
            eaters=['bar:default', 'baz:default'])
        self.heaven.avatars[a.avatarId] = a
        a2 = FakeComponentAvatar(name='bar', port=1000, listen_host='bar-host')
        self.heaven.avatars[a2.avatarId] = a2
        a3 = FakeComponentAvatar(name='baz', port=1001, listen_host='baz-host')
        self.heaven.avatars[a2.avatarId] = a3

        set = self.heaven._getFeederSet(a)
        set.addFeeders(a2)
        set.addFeeders(a3)

class FakeTransport:
    def getPeer(self):
        from twisted.internet.address import IPv4Address
        return IPv4Address('TCP', 'nullhost', 1)
    def getHost(self):
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
        return range(7600,7610)

    def remote_create(self, avatarId, type, moduleName, methodName, config):
        self.debug('remote_create(%s): logging in component' % avatarId)
        avatar = self.testcase._loginComponent(self.avatarId,
            avatarId, moduleName, methodName, type, config)
        # need to return the avatarId for comparison
        return avatarId

class FakeComponentMind(FakeMind):

    logCategory = 'fakecomponentmind'

    def __init__(self, testcase, workerName, avatarId, type,
        moduleName, methodName, config):
        FakeMind.__init__(self, testcase)

        self.info('Creating component mind for %s' % avatarId)
        state = planet.ManagerJobState()
        state._dict = {
            'type': type,
            'pid': 1,
            'cpu': 0.1,
            'mood': moods.waking.value,
            'ip': '0.0.0.0',
            'workerName': workerName,
            'feederNames': [],
            'eaterNames': [] }
        self.state = state

    def remote_getState(self):
        self.debug('remote_getState: returning %r' % self.state)
        return self.state

    def remote_provideMasterClock(self, port):
        return ("127.0.0.1", port, 0L)

    def remote_setup(self, config):
        self.debug('remote_setup(%r)' % config)

    def remote_start(self, eatersData, feedersData, clocking):
        self.debug('remote_start(%r, %r)' % (eatersData, feedersData))
        self.testcase.failUnless(hasattr(self, 'state'))
        self.testcase.failUnless(hasattr(self.state, 'observe_set'))
        
        self.state.observe_set('mood', moods.happy.value)
    
class TestVishnu(log.Loggable, unittest.TestCase):

    logCategory = "TestVishnu"

    def setUp(self):
        # load and verify registry
        from flumotion.common import registry
        reg = registry.getRegistry()

        self.vishnu = manager.Vishnu('test', unsafeTracebacks=1)
        self._workers = {}    # id -> avatar
        self._components = {} # id -> avatar

    # helper functions
    def _loginWorker(self, avatarId):
        # create a worker and log it in
        # return the avatar

        # log in a worker
        mind = FakeWorkerMind(self, avatarId)

        tuple = self.vishnu.dispatcher.requestAvatar(avatarId, None,
            mind, pb.IPerspective, interfaces.IWorkerMedium)

        avatar = tuple[1]

        # hack for cleanup
        avatar._tuple = tuple
        avatar._mind = mind
        avatar._avatarId = avatarId

        # trigger attached
        # twisted 2.2.0 TestCase does not have a runReactor method
        # and according to twisted changeset 15556 it was always
        # deprecated
        from twisted.internet import reactor
        reactor.iterate()
        self._workers[avatarId] = avatar
        return avatar

    def _loginComponent(self, workerName, avatarId, type, moduleName,
        methodName, config):
        # create a component and log it in
        # return the avatar

        mind = FakeComponentMind(self, workerName, avatarId, type,
            moduleName, methodName, config)

        tuple = self.vishnu.dispatcher.requestAvatar(avatarId, None,
            mind, pb.IPerspective, interfaces.IComponentMedium)

        avatar = tuple[1]

        # hack for cleanup
        avatar._tuple = tuple
        avatar._mind = mind
        avatar._avatarId = avatarId

        # trigger attached
        # twisted 2.2.0 TestCase does not have a runReactor method
        # and according to twisted changeset 15556 it was always
        # deprecated
        from twisted.internet import reactor
        reactor.iterate()
    
        self._components[avatarId] = avatar
        return avatar

    def _logoutAvatar(self, avatar):
        # log out avatar
        logout = avatar._tuple[2]
        mind = avatar._mind
        avatarId = avatar._avatarId

        logout(avatar, mind, avatarId)
        
        # trigger detached
        # twisted 2.2.0 TestCase does not have a runReactor method
        # and according to twisted changeset 15556 it was always
        # deprecated
        from twisted.internet import reactor
        reactor.iterate()

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
        
        self.vishnu.loadConfigurationXML(file, manager.RUNNING_LOCALLY)
        s = self.vishnu.state
        
        l = s.get('flows')
        self.failUnless(l)
        f = l[0]
        self.failUnlessEqual(f.get('name'), 'testflow')
        
        l = f.get('components')
        self.failUnless(l)

        # FIXME: why a second time ? Maybe to check that reloading doesn't
        # change things ?
        self.vishnu.loadConfigurationXML(file, manager.RUNNING_LOCALLY)

    def testConfigBeforeWorker(self):
        # test a config with three components being loaded before the worker
        # logs in
        mappers = self.vishnu._componentMappers

        # test loading of a config, logging in the component and worker,
        # and their cleanup
        __thisdir = os.path.dirname(os.path.abspath(__file__))
        file = os.path.join(__thisdir, 'test.xml')
        
        self.vishnu.loadConfigurationXML(file, manager.RUNNING_LOCALLY)

        # verify component mapper
        # 3 component states + avatarId's gotten from the config
        self.assertEqual(len(mappers.keys()), 6)

        # verify dag edges
        id = '/testflow/producer-video-test'
        state = mappers[id].state
        assert not state, state
        o = self.vishnu._dag.getOffspring(state)
        names = [s.get('name') for s in o]
        self.failIf('producer-video-test' in names)
        self.failUnless('converter-ogg-theora' in names)
        self.failUnless('streamer-ogg-theora' in names)
        
        # log in a worker and verify components get started
        avatar = self._loginWorker('worker')

        self._verifyConfigAndOneWorker()

        # log out the producer and verify the mapper
        id = '/testflow/producer-video-test'
        avatar = self._components[id]
        m = mappers[avatar]

        self._logoutAvatar(avatar)

        #import pprint
        #pprint.pprint(mappers.keys())
        self.assertEqual(len(mappers.keys()), 8)

        self._verifyComponentIdGone(id)

        # log out the converter and verify
        id = '/testflow/converter-ogg-theora'
        m = mappers[id]
        avatar = self._components[id]
        self._logoutAvatar(avatar)

        self._verifyConfigAndNoWorker()
    testConfigBeforeWorker.skip = "Help, thomas..."

    def testConfigAfterWorker(self):
        # test a config with three components being loaded after the worker
        # logs in
        mappers = self.vishnu._componentMappers

        __thisdir = os.path.dirname(os.path.abspath(__file__))
        file = os.path.join(__thisdir, 'test.xml')

        # log in worker
        avatar = self._loginWorker('worker')
        self.failUnlessEqual(len(self._workers), 1)
        self.failUnlessEqual(len(self._components), 0)
        
        # load configuration
        self.vishnu.loadConfigurationXML(file, manager.RUNNING_LOCALLY)

        self._verifyConfigAndOneWorker()
        
        # log out the producer and verify the mapper
        id = '/testflow/producer-video-test'
        avatar = self._components[id]
        m = mappers[avatar]

        self._logoutAvatar(avatar)

        #import pprint
        #pprint.pprint(mappers.keys())
        self.assertEqual(len(mappers.keys()), 8)

        self._verifyComponentIdGone(id)
        
        # log out the converter and verify
        id = '/testflow/converter-ogg-theora'
        m = mappers[id]
        avatar = self._components[id]
        self._logoutAvatar(avatar)

        self._verifyConfigAndNoWorker()

        # clear out the complete planet
        d = self.vishnu.emptyPlanet()
        if weHaveAnOldTwisted():
            unittest.deferredResult(d)
            self.assertEqual(len(mappers.keys()), 0)
        else:
            def verifyMappersIsZero(result):
                self.assertEqual(len(mappers.keys()), 0)
            d.addCallback(verifyMappersIsZero)
            return d

    def _verifyConfigAndOneWorker(self):
        self.debug('verifying after having loaded config and started worker')
        mappers = self.vishnu._componentMappers

        # verify component mapper
        # all components should have gotten started, and logged in
        self.failUnlessEqual(len(self._components), 2)
        self.assertEqual(len(mappers.keys()), 10,
            "keys: %r of length %d != 10" % (
                mappers.keys(), len(mappers.keys())))

        keys = self._components.keys()
        self.failUnless('/testflow/producer-video-test' in keys)
        self.failUnless('/testflow/converter-ogg-theora' in keys)

        # verify mapper
        # 1 component with state and id
        # 2 components with state, avatar, id, and jobstate
        self.assertEqual(len(mappers.keys()), 10)

        id = '/testflow/producer-video-test'
        avatar = self._components[id]
        self.failUnless(id in mappers.keys())
        self.failUnless(avatar in mappers.keys())

        m = mappers[id]

        self.assertEqual(m.id, id)
        self.assertEqual(m.avatar, avatar)
        self.failUnless(m.state)
        self.failUnless(m.jobState)

        state = m.jobState
        l = MyListener()
        state.addListener(l)
        d = l.notifyOnSet(state, 'mood', moods.happy.value)
        if weHaveAnOldTwisted():
            unittest.deferredResult(d)
            self.assertEqual(state.get('mood'), moods.happy.value,
                "mood of %s is not happy but %r" % (
                    m.state.get('name'), moods.get(state.get('mood'))))
            # verify the component avatars
            self.failUnless(avatar.jobState)
            self.failUnless(avatar.componentState)
        else:
            def verifyMoodIsHappy(result):
                self.assertEqual(state.get('mood'), moods.happy.value,
                    "mood of %s is not happy but %r" % (
                        m.state.get('name'), moods.get(state.get('mood'))))
                # verify the component avatars
                self.failUnless(avatar.jobState)
                self.failUnless(avatar.componentState)
            d.addCallback(verifyMoodIsHappy)
        
    def _verifyConfigAndNoWorker(self):
        mappers = self.vishnu._componentMappers

        # verify mapper
        self.assertEqual(len(mappers.keys()), 6)
        self._verifyComponentIdGone('/testflow/converter-ogg-theora')
        self._verifyComponentIdGone('/testflow/producer-video-test')

    def _verifyComponentIdGone(self, id):
        # verify logged out components
        mappers = self.vishnu._componentMappers
        m = mappers[id]
        avatar = self._components[id]
  
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

