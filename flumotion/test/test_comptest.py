# -*- Mode: Python -*-
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

import sys

from twisted.internet import defer, reactor, selectreactor, gtk2reactor

from flumotion.common import testsuite
from flumotion.common import log, errors
from flumotion.common.planet import moods
from flumotion.component.producers.pipeline.pipeline import Producer
from flumotion.component.converters.pipeline.pipeline import Converter
from flumotion.test import comptest
from flumotion.test.comptest import ComponentTestHelper, ComponentWrapper, \
    CompTestTestCase, ComponentSad, pipeline_src, pipeline_cnv

attr = testsuite.attr


class TestCompTestGtk2Reactorness(testsuite.TestCase):
    supportedReactors = []

    def testGtk2Supportness(self):

        class TestCompTestSupportedReactors(CompTestTestCase):

            def runTest(self):
                pass

        obj = TestCompTestSupportedReactors('runTest')
        if not isinstance(sys.modules['twisted.internet.reactor'],
                          gtk2reactor.Gtk2Reactor):
            # not running with a gtk2reactor, the TestCompTestSupportedReactors
            # instance should have a 'skip' attribute
            self.failUnless(hasattr(obj, 'skip'),
                            "setting supportedReactors doesn't set 'skip'"
                            " correctly.")
        else:
            self.failIf(hasattr(obj, 'skip'),
                        "setting supportedReactors sets 'skip' incorrectly.")


class TestComponentWrapper(testsuite.TestCase):

    def tearDown(self):
        # The components a.t.m. don't cleanup after
        # themselves too well, remove when fixed.
        # See also a similar snippet in TestCompTestFlow.tearDown()
        comptest.cleanup_reactor()

    def testGetUniqueName(self):
        self.failIfEquals(ComponentWrapper.get_unique_name(),
                          ComponentWrapper.get_unique_name())

    def testInvalidType(self):
        self.failUnlessRaises(errors.UnknownComponentError,
                              ComponentWrapper, 'invalid-comp-type',
                              None)

    def testValidType(self):
        cw = ComponentWrapper('pipeline-producer', None, name='pp')
        self.assertEquals(cw.cfg,
                          {'feed': ['default'], 'name': 'pp',
                           'parent': 'default', 'clock-master': None,
                           'avatarId': '/default/pp', 'eater': {},
                           'source': [], 'plugs': {}, 'properties': {},
                           'type': 'pipeline-producer'})

    def testSimpleLink(self):
        pp = ComponentWrapper('pipeline-producer', None, name='pp')
        pc = ComponentWrapper('pipeline-converter', None)

        pp.feed(pc)
        self.assertEquals(pc.cfg['source'], ['pp:default'])
        self.assertEquals(pc.cfg['eater'], {'default':
                                            [('pp:default', 'default')]})

    def testNonDefaultLink(self):
        fwp = ComponentWrapper('firewire-producer', None, name='fwp')
        pc = ComponentWrapper('pipeline-converter', None, name='pc')

        # this should raise an exception - firewire-producer doesn't
        # have a default feeder
        self.failUnlessRaises(comptest.ComponentTestException, fwp.feed, pc)

        fwp.feed(pc, [('video', 'default')])
        fwp.feed(pc, [('audio', 'default')])

        self.assertEquals(pc.cfg['source'], ['fwp:video', 'fwp:audio'])
        self.assertEquals(pc.cfg['eater'],
                          {'default': [('fwp:video', 'default'),
                                       ('fwp:audio', 'default-bis')]})

    def testInstantiateErrors(self):
        # this passes None as the class name for ComponentWrapper,
        # i.e. it tries to dynamically subclass None. Throws a "cannot
        # instantiate None" error
        pp = ComponentWrapper('pipeline-producer', None, name='pp')
        self.failUnlessRaises(TypeError, pp.instantiate)

        # missing mandatory pipeline property
        pp = ComponentWrapper('pipeline-producer', Producer,
                              name='pp')
        d = pp.instantiate()
        # See the comment in test_setup_fail_gst_linking()
        return self.failUnlessFailure(d, ComponentSad)

    def testGstreamerError(self):
        pp = ComponentWrapper('pipeline-producer', Producer,
                              name='pp', props={'pipeline': 'fakesink'})

        d = pp.instantiate()
        # See the comment in test_setup_fail_gst_linking()
        return self.failUnlessFailure(d, ComponentSad)


class TestCompTestSetup(CompTestTestCase):

    def setUp(self):
        self.prod = pipeline_src()
        self.cnv1 = pipeline_cnv()
        self.cnv2 = pipeline_cnv()
        self.components = [self.prod, self.cnv1, self.cnv2]

        self.p = ComponentTestHelper()

    def tearDown(self):
        d = defer.DeferredList([c.stop() for c in self.components])
        # The components a.t.m. don't cleanup after
        # themselves too well, remove when fixed.
        # See also a similar snippet in TestCompTestFlow.tearDown()
        d.addCallback(comptest.cleanup_reactor)
        return d

    def testTrivial(self):
        # This fails without having cleanup_reactor() in tearDown()
        return defer.succeed(None)

    def testSuccess(self):
        pp = ComponentWrapper('pipeline-producer', Producer,
                              name='pp', props={'pipeline':
                                                'audiotestsrc is-live=1'},
                              cfg={'clock-master': '/default/pp'})

        d = pp.instantiate()
        d.addCallback(lambda _: pp.wait_for_mood(moods.happy))
        d.addCallback(lambda _: pp.stop())
        return d

    def testAutoLinking(self):
        # the components should be linked automatically
        # [prod:default] --> [default:cnv1:default] --> [default:cnv2]
        self.p.set_flow([self.prod, self.cnv1, self.cnv2])

        prod_feed = '%s:%s' % (self.prod.name, self.prod.cfg['feed'][0])
        self.assertEquals([prod_feed], self.cnv1.cfg['source'])
        self.assertEquals({'default': [(prod_feed, 'default')]},
                          self.cnv1.cfg['eater'])

        cnv1_feed = '%s:%s' % (self.cnv1.name, self.cnv1.cfg['feed'][0])
        self.assertEquals([cnv1_feed], self.cnv2.cfg['source'])
        self.assertEquals({'default': [(cnv1_feed, 'default')]},
                          self.cnv2.cfg['eater'])

    def testDontAutoLinkLinked(self):
        p2 = pipeline_src()
        self.components.append(p2)

        p2.feed(self.cnv1)
        self.prod.auto_link = False

        # [  p2:default] --> [default:cnv1], set explicitly
        # no p2 --> prod, explicitly prohibited
        # [prod:default] --> [default:cnv2]
        self.p.set_flow([p2, self.prod, self.cnv2, self.cnv1])

        prod_feed = '%s:%s' % (p2.name, p2.cfg['feed'][0])
        self.assertEquals([prod_feed], self.cnv1.cfg['source'])
        self.assertEquals({'default': [(prod_feed, 'default')]},
                          self.cnv1.cfg['eater'])

        self.assertEquals([], self.prod.cfg['source'])
        self.assertEquals({}, self.prod.cfg['eater'])

        prod_feed = '%s:%s' % (self.prod.name, self.prod.cfg['feed'][0])
        self.assertEquals([prod_feed], self.cnv2.cfg['source'])
        self.assertEquals({'default': [(prod_feed, 'default')]},
                          self.cnv2.cfg['eater'])

    def testMasterClock(self):
        p2 = pipeline_src()
        self.components.append(p2)

        p2.feed(self.cnv1)
        self.prod.feed(self.cnv1)
        self.cnv1.feed(self.cnv2)

        self.p.set_flow([self.prod, p2, self.cnv1, self.cnv2], auto_link=False)

        # both prod and p2 require a clock, only one should provide it
        self.assertEquals(self.prod.cfg['clock-master'],
                          p2.cfg['clock-master'])
        self.assertEquals(self.cnv1.cfg['clock-master'], None)
        self.assertEquals(self.cnv2.cfg['clock-master'], None)

        master = self.prod
        slave = p2
        if master.cfg['clock-master'] != master.cfg['avatarId']:
            slave, master = master, slave

        # the master-clock component should provide a clock, and not
        # require an external clock source, as opposed the the slave
        self.assertEquals(master.sync, None)
        self.failIfEquals(slave.sync, None)


class TestCompTestFlow(CompTestTestCase):

    slow = True

    def setUp(self):
        self.duration = 2.0

        prod_pp = ('videotestsrc is-live=true ! '
                   'video/x-raw-rgb,framerate=(fraction)8/1,'
                   'width=32,height=24')
        self.prod = pipeline_src(prod_pp)

        self.cnv1 = pipeline_cnv()
        self.cnv2 = pipeline_cnv()

        self.p = ComponentTestHelper()

    def tearDown(self):
        d = self.p.stop_flow()

        # add cleanup, otherwise components a.t.m. don't cleanup after
        # themselves too well, remove when fixed
        d.addBoth(lambda _: comptest.cleanup_reactor())
        return d

    def testSetupFailGstLinking(self):
        p2 = pipeline_src('fakesink') # this just can't work!
        c2 = pipeline_cnv('fakesink') # and neither can this!

        # we're going to fail in gst - make sure the gst logger is silent
        import gst
        old_debug_level = gst.debug_get_default_threshold()
        gst.debug_set_default_threshold(gst.LEVEL_NONE)

        self.p.set_flow([p2, c2, self.cnv1])
        d = self.p.start_flow()

        if old_debug_level != gst.LEVEL_NONE:

            def _restore_gst_debug_level(rf):
                gst.debug_set_default_threshold(old_debug_level)
                return rf
            d.addBoth(_restore_gst_debug_level)
        # Because component setup errors get swallowed in
        # BaseComponent.setup() we won't get the exact error that will
        # be thrown, i.e. PipelineParseError. Instead, the component
        # will turn sad and we will get a ComponentSad failure from
        # the ComponentWrapper.
        return self.failUnlessFailure(d, ComponentSad)

    def testSetupStartedAndHappy(self):
        flow = [self.prod, self.cnv1, self.cnv2]
        self.p.set_flow(flow)
        d = self.p.start_flow()

        def wait_for_happy(_):
            self.debug('Waiting for happiness')
            d = defer.DeferredList(
                [c.wait_for_mood(moods.happy) for c in flow])
            d.addCallback(check_happy)
            return d

        def check_happy(_):
            self.debug('Checking for happiness')
            for c in flow:
                self.assertEquals(moods.get(c.comp.getMood()), moods.happy)
            return _

        d.addCallback(wait_for_happy)
        return d

    def testRunFailGstLinking(self):
        p2 = pipeline_src('fakesink') # this just can't work!
        c2 = pipeline_cnv('fakesink') # and neither can this!

        # we're going to fail in gst - make sure the gst logger is silent
        import gst
        old_debug_level = gst.debug_get_default_threshold()
        gst.debug_set_default_threshold(gst.LEVEL_NONE)

        self.p.set_flow([p2, c2, self.cnv1])
        d = self.p.run_flow(self.duration)

        if old_debug_level != gst.LEVEL_NONE:

            def _restore_gst_debug_level(rf):
                gst.debug_set_default_threshold(old_debug_level)
                return rf
            d.addBoth(_restore_gst_debug_level)
        # See the comment in test_setup_fail_gst_linking()
        return self.failUnlessFailure(d, ComponentSad)

    def testRunStartTimeout(self):
        start_delay_time = 5.0
        self.p.guard_timeout = 2.0

        class LingeringCompWrapper(ComponentWrapper):

            def instantiate(self, *a, **kw):
                d = ComponentWrapper.instantiate(self, *a, **kw)

                def delay_start(result):
                    dd = defer.Deferred()
                    reactor.callLater(start_delay_time, dd.callback, result)
                    return dd
                d.addCallback(delay_start)
                return d
        c2 = LingeringCompWrapper('pipeline-converter', Converter,
                                  props={'pipeline': 'identity'})
        self.p.set_flow([self.prod, c2])
        d = self.p.run_flow(self.duration)
        return self.failUnlessFailure(d, comptest.StartTimeout)

    def testRunWithDelays(self):
        flow = [self.prod, self.cnv1, self.cnv2]
        self.p.start_delay = 0.5

        self.p.set_flow(flow)
        return self.p.run_flow(self.duration)

    def testRunProvidesClocking(self):
        p2_pp = ('videotestsrc is-live=true ! '
                 'video/x-raw-rgb,framerate=(fraction)8/1,'
                 'width=32,height=24')
        p2 = pipeline_src(p2_pp)

        from flumotion.component.muxers.multipart import Multipart
        mux = ComponentWrapper('multipart-muxer', Multipart, name='mux')

        self.prod.feed(mux)
        p2.feed(mux)
        mux.feed(self.cnv1)

        self.clock_slave = p2

        def check_clocking(_):
            self.warning('check_clocking: %s %r' %
                         (self.clock_slave.name,
                          self.clock_slave.comp.pipeline.get_clock()))
            import gst
            pp = self.clock_slave.comp.pipeline
            # is there a better way to check if that component is
            # using an external clock source?
            self.failUnless(isinstance(pp.get_clock(), gst.NetClientClock),
                            "Didn't receive external clocking info.")
            return _
        task_d = defer.Deferred()
        task_d.addCallback(check_clocking)

        self.p.set_flow([self.prod, p2, mux, self.cnv1], auto_link=False)
        if self.prod is not self.p._master:
            # p2 (of [self.prod, p2]) seems to be the master this time
            self.clock_slave = self.prod
        d = self.p.run_flow(self.duration, tasks=[task_d])
        return d

    def testRunTasksChainedAndFired(self):
        self.tasks_fired = []
        self.tasks = []
        num_tasks = 5

        def tasks_started(result, index):
            self.tasks_fired[index] = True
            return result

        def tasks_check(result):
            self.failIfIn(False, self.tasks_fired)
            self.failIfIn(False, self.tasks_fired)
            return result
        for i in range(num_tasks):
            self.tasks_fired.append(False)
            d = defer.Deferred()
            self.tasks.append(d)
            d.addCallback(tasks_started, i)

        self.p.set_flow([self.prod, self.cnv1, self.cnv2])
        d = self.p.run_flow(self.duration, tasks=self.tasks)
        d.addCallback(tasks_check)

        return d

    def testRunTasksTimeout(self):
        self.p.set_flow([self.prod, self.cnv1, self.cnv2])
        self.p.guard_timeout = 4.0

        def make_eternal_deferred(_):
            # never going to fire this one...
            eternal_d = defer.Deferred()
            return eternal_d
        task_d = defer.Deferred()
        task_d.addCallback(make_eternal_deferred)

        d = self.p.run_flow(self.duration, tasks=[task_d])

        return self.failUnlessFailure(d, comptest.FlowTimeout)

    def testRunStopTimeout(self):
        stop_delay_time = 6.0
        self.p.guard_timeout = 4.0

        class DelayingCompWrapper(ComponentWrapper):
            do_delay = True

            def stop(self, *a, **kw):
                d = ComponentWrapper.stop(self, *a, **kw)

                def delay_stop(result):
                    if self.do_delay:
                        self.do_delay = False
                        dd = defer.Deferred()
                        reactor.callLater(stop_delay_time, dd.callback, result)
                        return dd
                    return result
                d.addCallback(delay_stop)
                return d
        c2 = DelayingCompWrapper('pipeline-converter', Converter,
                                 props={'pipeline': 'identity'})
        self.p.set_flow([self.prod, c2])
        d = self.p.run_flow(self.duration)
        return self.failUnlessFailure(d, comptest.StopTimeout)

    def testRunStartedThenFails(self):
        self.p.set_flow([self.prod, self.cnv1, self.cnv2])
        wrench_timeout = 0.5

        class CustomWrenchException(Exception):
            pass

        def insert_wrenches_into_cogs(_):

            def insert_wrench(c):
                raise CustomWrenchException("Wasn't that loose?")
            d = defer.Deferred()
            d.addCallback(insert_wrench)
            reactor.callLater(wrench_timeout, d.callback, self.cnv1)
            return d
        task_d = defer.Deferred()
        task_d.addCallback(insert_wrenches_into_cogs)

        d = self.p.run_flow(self.duration, tasks=[task_d])
        return self.failUnlessFailure(d, CustomWrenchException)

    def testRunStartedThenFlowAndStopFail(self):
        flow_error_timeout = 0.5

        class CustomFlowException(Exception):
            pass

        class CustomStopException(Exception):
            pass

        class BrokenCompWrapper(ComponentWrapper):
            do_break = True

            def stop(self, *a, **kw):
                d = ComponentWrapper.stop(self, *a, **kw)

                def delay_stop(result):
                    # breaking once should be enough
                    if self.do_break:
                        self.do_break = False
                        raise CustomStopException()
                d.addCallback(delay_stop)
                return d
        c2 = BrokenCompWrapper('pipeline-converter', Converter,
                               props={'pipeline': 'identity'})
        self.p.set_flow([self.prod, c2])

        class CustomFlowException(Exception):
            pass

        def insert_flow_errors(_):

            def insert_error(_ignore):
                raise CustomFlowException("Exception!")
            d = defer.Deferred()
            d.addCallback(insert_error)
            reactor.callLater(flow_error_timeout, d.callback, None)
            return d
        task_d = defer.Deferred()
        task_d.addCallback(insert_flow_errors)
        d = self.p.run_flow(self.duration, tasks=[task_d])
        return self.failUnlessFailure(d, CustomFlowException)
