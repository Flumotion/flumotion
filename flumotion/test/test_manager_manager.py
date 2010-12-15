# -*- Mode: Python; test-case-name: flumotion.test.test_manager_manager -*-
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

import os

from twisted.spread import pb
from twisted.internet import defer, reactor
from zope.interface import implements

from flumotion.common import log, planet, interfaces, common
from flumotion.common import errors
from flumotion.common import testsuite
from flumotion.common.planet import moods
from flumotion.manager import component, manager
from flumotion.twisted import flavors


class MyListener(log.Loggable):
    # a helper object that you can get deferreds from that fire when
    # a certain state has a certain key set to a certain value
    implements(flavors.IStateListener)

    def __init__(self, state):
        self._setters = {} # (state, key, value) tuple -> list of deferred
        state.addListener(self, set_=self.stateSet)

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
                self.debug("firing deferred %s" % d)
                d.callback(None)
            del self._setters[t]


class FakeComponentAvatar(log.Loggable):
    ### since we fake out componentavatar, eaters need to be specified fully
    ### for the tests, ie sourceComponentName:feedName

    def __init__(self, name='fake', parent='eve', eaters=[], port=-1,
                 listen_host='127.0.0.1'):
        self.name = name
        self.parent = parent
        self.avatarId = common.componentId(parent, name)
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


class TestComponentMapper(testsuite.TestCase):

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

        class FakeAvatar:
            pass
        avatar = FakeAvatar()
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

                def gotResult(res):
                    self.debug('callRemote(%s) succeeded with %r', name, res)
                    return res
                d = defer.maybeDeferred(m, *args, **kwargs)
                d.addCallback(gotResult)
                return d
            except Exception, e:
                self.warning('callRemote(%s) failed with %s' % (
                    name, log.getExceptionMessage(e)))
                return defer.fail(e)
        else:
            raise AttributeError('no method %s on self %r' % (name, self))


class FakeWorkerMind(FakeMind):

    logCategory = 'fakeworkermind'

    def __init__(self, testcase, avatarId):
        FakeMind.__init__(self, testcase)
        self.avatarId = avatarId
        self._createDeferreds = []

    def remote_getPorts(self):
        return (range(7600,
                      7608), False)

    def remote_getFeedServerPort(self):
        return 7609

    def remote_create(self, avatarId, type, moduleName, methodName, nice,
            config):
        self.debug('remote_create(%s): logging in component' % avatarId)
        d = self.testcase._loginComponent(self.avatarId,
            avatarId, moduleName, methodName, type, config)

        d2 = defer.Deferred()
        self._createDeferreds.append(d2)
        d.addCallback(lambda _: d2.callback(avatarId))

        # need to return the avatarId for comparison
        d.addCallback(lambda _: avatarId)
        return d

    def waitForComponentsCreate(self):
        d = defer.DeferredList(self._createDeferreds)
        self._createDeferreds = []
        return d

    def remote_getComponents(self):
        # Fire only asychronously; with an empty list.
        d = defer.Deferred()
        reactor.callLater(0, d.callback, [])
        return d


class FakeComponentMind(FakeMind):

    logCategory = 'fakecomponentmind'

    def __init__(self, testcase, workerName, avatarId, type,
        moduleName, methodName, config):
        FakeMind.__init__(self, testcase)
        self.avatarId = avatarId
        self.logName = avatarId
        self.config = config

        self.info('Creating component mind for %s' % avatarId)
        state = planet.ManagerJobState()
        state._dict = {
            'type': type,
            'pid': 1,
            'mood': moods.waking.value,
            'manager-ip': '0.0.0.0',
            'workerName': workerName,
            'feederNames': [],
            'eaterNames': [],
            'messages': []}
        self.state = state

    def remote_getState(self):
        self.debug('remote_getState: returning %r' % self.state)
        return self.state

    def remote_getConfig(self):
        return self.config

    def remote_getMasterClockInfo(self):
        return None

    def remote_provideMasterClock(self, port):
        # Turn happy; we must do this asynchronously, otherwise the tests
        # synchronously log out a client where that shouldn't be possible.

        def turnHappy():
            self.state.observe_set('mood', moods.happy.value)
        reactor.callLater(0, turnHappy)

        return ("127.0.0.1", port, 0L)

    def remote_setMasterClock(self, ip, port, base_time):
        return None

    def remote_eatFrom(self, eaterAlias, fullFeedId, host, port):
        # pretend this works
        return

    def remote_feedTo(self, componentId, feedId, host, port):
        # pretend this works
        return


class TestVishnu(testsuite.TestCase):

    logCategory = "TestVishnu"

    def setUp(self):
        # load and verify registry
        from flumotion.common import registry
        reg = registry.getRegistry()

        self.vishnu = manager.Vishnu('test', unsafeTracebacks=1)
        self._workers = {}    # id -> avatar
        self._components = {} # id -> avatar

    # helper functions

    def _requestAvatar(self, avatarId, mind, iface, avatarDict):
        d = self.vishnu.dispatcher.requestAvatar(avatarId, None,
            mind, pb.IPerspective, iface)

        def got_result((iface, avatar, cleanup)):
            # hack for cleanup
            avatar._cleanup = cleanup
            avatar._mind = mind
            avatar._avatarId = avatarId

            avatarDict[avatarId] = avatar
            return avatar
        d.addCallback(got_result)
        return d

    def _loginWorker(self, avatarId):
        # create a worker and log it in
        # return the avatar

        # log in a worker
        return self._requestAvatar(avatarId,
                                   FakeWorkerMind(self, avatarId),
                                   interfaces.IWorkerMedium,
                                   self._workers)

    def _loginComponent(self, workerName, avatarId, type, moduleName,
            methodName, config):
        # create a component and log it in
        # return the avatar

        mind = FakeComponentMind(self, workerName, avatarId, type,
            moduleName, methodName, config)
        return self._requestAvatar(avatarId, mind,
                                   interfaces.IComponentMedium,
                                   self._components)

    def _logoutAvatar(self, avatar):
        # log out avatar
        self.debug('_logoutAvatar %r' % avatar)
        logout = avatar._cleanup
        mind = avatar._mind
        avatarId = avatar._avatarId

        logout(avatarId, avatar, mind)

    def testWorker(self):
        names = self.vishnu.workerHeaven.state.get('names')
        self.failUnlessEqual(len(names), 0)

        def got_avatar(avatar):
            # check
            names = self.vishnu.workerHeaven.state.get('names')
            self.failUnlessEqual(len(names), 1)
            self.failUnless('worker' in names)

            self._logoutAvatar(avatar)

            # check
            names = self.vishnu.workerHeaven.state.get('names')
            self.failUnlessEqual(len(names), 0)

        d = self._loginWorker('worker')
        d.addCallback(got_avatar)
        return d

    def testLoadConfiguration(self):
        __thisdir = os.path.dirname(os.path.abspath(__file__))
        file = os.path.join(__thisdir, 'test.xml')

        self.vishnu.loadComponentConfigurationXML(file, manager.LOCAL_IDENTITY)
        s = self.vishnu.state

        l = s.get('flows')
        self.failUnless(l)
        f = l[0]
        self.failUnlessEqual(f.get('name'), 'testflow')

        l = f.get('components')
        self.failUnless(l)

        # FIXME: why a second time ? Maybe to check that reloading doesn't
        # change things ?
        self.vishnu.loadComponentConfigurationXML(file, manager.LOCAL_IDENTITY)

        # now lets empty planet
        return self.vishnu.emptyPlanet()

    def testLoadComponentWithSynchronization(self):

        def loadProducer():
            compType = "pipeline-producer"
            compId = common.componentId("testflow", "producer-video-test")
            compProps = [
                ("pipeline", "videotestsrc ! video/x-raw-yuv,width=320,"
                 "height=240,framerate=5/1,format=(fourcc)I420")]
            return self.vishnu.loadComponent(manager.LOCAL_IDENTITY,
                                             compType, compId, None, compProps,
                                             "worker", [], [], False, [])
        # Add more tests if you implement handling of sync-needing components
        self.assertRaises(NotImplementedError, loadProducer)

    def testLoadComponent(self):

        def loadProducerFromFile():
            __thisdir = os.path.dirname(os.path.abspath(__file__))
            file = os.path.join(__thisdir, 'testLoadComponent.xml')
            return self.vishnu.loadComponentConfigurationXML(
                file, manager.LOCAL_IDENTITY)

        def loadConverter(_):
            flows = self.vishnu.state.get('flows')
            self.assertEqual(len(flows), 1)
            flow = flows[0]
            self.assertEqual(flow.get('name'), 'testflow')
            components = flow.get('components')
            self.assertEqual(len(components), 1)
            self.assertEqual(components[0].get('name'),
                             "producer-video-test")

            compType = "pipeline-converter"
            compId = common.componentId("testflow", "converter-ogg-theora")
            compEaters = [("default", "producer-video-test")]
            compProps = [("pipeline", "ffmpegcolorspace ! theoraenc "
                         "keyframe-force=5 ! oggmux")]
            compState = self.vishnu.loadComponent(
                manager.LOCAL_IDENTITY, compType, compId, None, compProps,
                "worker", [], compEaters, False, [])

            self.assertEqual(compState.get('config').get('name'),
                             "converter-ogg-theora")
            self.failIf('label' in compState.get('config'))
            self.assertEqual(len(components), 2)
            self.assertEqual(components[1].get('name'),
                             "converter-ogg-theora")

            # Loading the same component again raises an error
            self.assertRaises(errors.ComponentAlreadyExistsError,
                              self.vishnu.loadComponent,
                              manager.LOCAL_IDENTITY, compType, compId,
                              None, compProps, "worker", [], compEaters,
                              False, [])

            compType = "http-streamer"
            compId = common.componentId("testflow", "streamer-ogg-theora")
            compLabel = "Streamer OGG-Theora/Vorbis"
            compEaters = [("default", "converter-ogg-theora")]
            compProps = [("port", "8800")]
            compState = self.vishnu.loadComponent(
                manager.LOCAL_IDENTITY, compType, compId, compLabel,
                compProps, "streamer", [], compEaters, False, [])

            self.assertEqual(compState.get('config').get('name'),
                             "streamer-ogg-theora")
            self.assertEqual(compState.get('config').get('label'),
                             "Streamer OGG-Theora/Vorbis")
            self.assertEqual(len(components), 3)
            self.assertEqual(components[2].get('name'),
                             "streamer-ogg-theora")

            # Load a component to atmosphere
            compType = "ical-bouncer"
            compId = common.componentId("atmosphere", "test-bouncer")
            compProps = [("file", "icalfile")]
            compState = self.vishnu.loadComponent(
                manager.LOCAL_IDENTITY, compType, compId, None,
                compProps, "worker", [], [], False, [])

            atmosphere = self.vishnu.state.get('atmosphere')
            components = atmosphere.get('components')
            self.assertEquals(len(components), 1)
            self.failUnlessEqual(components[0].get('name'),
                                 'test-bouncer')

        d = loadProducerFromFile()
        d.addCallback(loadConverter)
        return d

    def testConfigBeforeWorker(self):
        # test a config with three components being loaded before the worker
        # logs in
        mappers = self.vishnu._componentMappers

        # test loading of a config, logging in the component and worker,
        # and their cleanup
        __thisdir = os.path.dirname(os.path.abspath(__file__))
        file = os.path.join(__thisdir, 'test.xml')

        def confLoaded(_):
            # verify component mapper
            # 3 component states + avatarId's gotten from the config
            self.assertEqual(len(mappers.keys()), 6)
            id = '/testflow/producer-video-test'
            state = mappers[id].state
            assert state, state

            # log in a worker and verify components get started
            return self._loginWorker('worker')

        def gotWorker(workerAvatar):
            d = workerAvatar.mind.waitForComponentsCreate()
            d.addCallback(lambda _: self._verifyConfigAndOneWorker())
            d.addCallback(lambda _: workerAvatar)
            return d

        def confChecked(workerAvatar):
            # log out the producer and verify the mapper
            id = '/testflow/producer-video-test'
            avatar = self._components[id]
            m = mappers[avatar]

            self._logoutAvatar(avatar)

            #import pprint
            #pprint.pprint(mappers.keys())
            self.assertEqual(len(mappers.keys()), 8)

            # We logged it out without it doing a clean shutdown, so it should
            # now be lost.
            self._verifyComponentIdGone(id, moods.lost)

            # log out the converter and verify
            id = '/testflow/converter-ogg-theora'
            m = mappers[id]
            avatar = self._components[id]
            # Pretend this one is a clean, requested shutdown.
            avatar._shutdown_requested = True
            self._logoutAvatar(avatar)

            # We requested shutdown, so this should now be sleeping.
            self._verifyComponentIdGone(id, moods.sleeping)

            self._verifyConfigAndNoWorker()

            # Now log out the worker.
            self._logoutAvatar(workerAvatar)

        d = self.vishnu.loadComponentConfigurationXML(
            file, manager.LOCAL_IDENTITY)
        d.addCallback(confLoaded)
        d.addCallback(gotWorker)
        d.addCallback(confChecked)
        return d
    testConfigBeforeWorker.skip = 'andy will definitely not fix this soon'

    def testConfigAfterWorker(self):
        # test a config with three components being loaded after the worker
        # logs in

        def loadConfigAndOneWorker(workerAvatar):
            log.debug('unittest', 'loadConfigAndOneWorker')
            self.failUnlessEqual(len(self._workers), 1)
            self.failUnlessEqual(len(self._components), 0)

            # load configuration
            d = self.vishnu.loadComponentConfigurationXML(
                file, manager.LOCAL_IDENTITY)
            d.addCallback(lambda _:
                          self._workers['worker'].mind.waitForComponentsCreate(
                ))
            d.addCallback(lambda _: self._verifyConfigAndOneWorker())
            d.addCallback(lambda _: workerAvatar)
            return d

        def logoutComponent(workerAvatar):
            log.debug('unittest', 'logoutComponent: producer')
            # log out the producer and verify the mapper
            id = '/testflow/producer-video-test'
            avatar = self._components[id]
            m = mappers[avatar]

            self._logoutAvatar(avatar)

            #import pprint
            #pprint.pprint(mappers.keys())
            self.assertEqual(len(mappers.keys()), 8)

            # We logged it out without it doing a clean shutdown, so it should
            # now be lost.
            self._verifyComponentIdGone(id, moods.lost)

            # log out the converter and verify
            log.debug('unittest', 'logoutComponent: converter')
            id = '/testflow/converter-ogg-theora'
            m = mappers[id]
            avatar = self._components[id]
            # Pretend this one is a clean, requested shutdown.
            avatar._shutdown_requested = True
            self._logoutAvatar(avatar)

            self._verifyComponentIdGone(id, moods.sleeping)

            log.debug('unittest', 'logoutComponent: _verifyConfigAndNoWorker')
            self._verifyConfigAndNoWorker()

            # Now log out the worker.
            log.debug('unittest', 'logoutComponent: _logoutAvatar')
            self._logoutAvatar(workerAvatar)

        def emptyPlanet(_):
            return self.vishnu.emptyPlanet()

        def verifyMappersIsZero(result):
            self.assertEqual(len(mappers.keys()), 0)

        mappers = self.vishnu._componentMappers
        __thisdir = os.path.dirname(os.path.abspath(__file__))
        file = os.path.join(__thisdir, 'test.xml')
        d = self._loginWorker('worker')
        d.addCallback(loadConfigAndOneWorker)
        d.addCallback(logoutComponent)
        d.addCallback(emptyPlanet)
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
        l = MyListener(state)
        self.debug("Waiting for component producer-video-test to go happy")
        d = l.notifyOnSet(state, 'mood', moods.happy.value)

        def verifyMoodIsHappy(result):
            self.debug("Turned happy")
            self.assertEqual(state.get('mood'), moods.happy.value,
                             "mood of %s is not happy but %r" % (
                m.state.get('name'), moods.get(state.get('mood'))))
            # verify the component avatars
            self.failUnless(avatar.jobState)
            self.failUnless(avatar.componentState)
        d.addCallback(verifyMoodIsHappy)
        return d

    def _verifyConfigAndNoWorker(self):
        mappers = self.vishnu._componentMappers

        # verify mapper
        self.assertEqual(len(mappers.keys()), 6)
        self._verifyComponentIdGone('/testflow/converter-ogg-theora')
        self._verifyComponentIdGone('/testflow/producer-video-test')

    def _verifyComponentIdGone(self, id, expectedMood=None,
            expectedMoodPending=None):
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
        if expectedMood: # Only check this if we had an expected mood passed
            self.assertEqual(state.get('mood'), expectedMood.value,
                '%s: mood is %s instead of %s' % (id,
                    moods.get(state.get('mood')), expectedMood))

        # always check moodPending
        moodPendingValue = state.get('moodPending')
        expectedValue = expectedMoodPending
        if expectedMoodPending is not None:
            expectedValue = expectedMoodPending.value
        self.assertEqual(moodPendingValue, expectedValue,
            '%s: moodPending is %r instead of %r' % (id,
                moodPendingValue is not None \
                    and moods.get(moodPendingValue) or 'None',
                expectedMoodPending))

        # verify avatar state
        self.failIf(avatar.jobState)
        self.failIf(avatar.componentState)

    def testDeleteFlow(self):
        __thisdir = os.path.dirname(os.path.abspath(__file__))
        file = os.path.join(__thisdir, 'test.xml')

        self.vishnu.loadComponentConfigurationXML(file, manager.LOCAL_IDENTITY)
        s= self.vishnu.state
        l = s.get('flows')
        self.failUnless(l)
        f = l[0]
        self.failUnlessEqual(f.get('name'), 'testflow')
        cs = f.get('components')
        self.failUnless(cs)

        self.assertRaises(ValueError, self.vishnu.deleteFlow, 'does-not-exist')

        cs[0].addKey('moodPending', True)
        self.assertRaises(errors.BusyComponentError,
                          self.vishnu.deleteFlow, 'testflow')
        cs[0].addKey('moodPending', None)

        # Test atomicity
        first = cs[0]
        cs[1].addKey('moodPending', True)
        self.assertRaises(errors.BusyComponentError,
                          self.vishnu.deleteFlow, 'testflow')
        cs[1].addKey('moodPending', None)
        self.failUnless(first in cs)

        self.vishnu.deleteFlow('testflow')
        l = s.get('flows')
        self.failIf(l)

        self.assertRaises(ValueError, self.vishnu.deleteFlow, 'testflow')

        # now lets empty planet
        return self.vishnu.emptyPlanet()

    def testUpdateBundlerBasket(self):
        basket = self.vishnu.getBundlerBasket()
        self.assertEqual(basket, self.vishnu.getBundlerBasket())
        # Force registry rebuild
        from flumotion.common import registry
        registry.getRegistry().verify(force=True)
        self.assertNotEqual(basket, self.vishnu.getBundlerBasket())
