# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008,2009 Fluendo, S.L.
# Copyright (C) 2010,2011 Flumotion Services, S.A.
# All rights reserved.
#
# This file may be distributed and/or modified under the terms of
# the GNU Lesser General Public License version 2.1 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.LGPL" in the source distribution for more information.
#
# Headers in this file shall remain intact.

import new
import os

from twisted.python import failure
from twisted.internet import reactor, defer, interfaces, gtk2reactor

from flumotion.common import registry, log, testsuite, common
from flumotion.common.planet import moods
from flumotion.component import feedcomponent
from flumotion.component.producers.pipeline.pipeline import Producer
from flumotion.component.converters.pipeline.pipeline import Converter
from flumotion.twisted import flavors

__all__ = ['ComponentTestHelper', 'ComponentWrapper',
           'CompTestTestCase', 'ComponentSad',
           'delayed_d', 'pipeline_src', 'pipeline_cnv']


class ComponentTestException(Exception):
    pass


class WrongReactor(ComponentTestException):
    pass


class StartTimeout(ComponentTestException):
    pass


class FlowTimeout(ComponentTestException):
    pass


class StopTimeout(ComponentTestException):
    pass


class ComponentSad(ComponentTestException):
    pass


def delayed_d(time, val):
    """Insert some delay into callback chain."""

    d = defer.Deferred()
    reactor.callLater(time, d.callback, val)
    return d


def override_value_callback(_result, value):
    """
    Ignore the result returned from the deferred callback chain and
    return the given value.
    """
    return value


def call_and_passthru_callback(result, callable_, *args, **kwargs):
    """Invoke the callable_ and passthrough the original result."""
    callable_(*args, **kwargs)
    return result


class CompTestTestCase(testsuite.TestCase):
    supportedReactors = [gtk2reactor.Gtk2Reactor]

    logCategory = 'comptest-test'


class ComponentWrapper(object, log.Loggable):
    logCategory = 'comptest-compwrap'
    _u_name_cnt = 0
    _registry = None

    def __init__(self, type_, class_, props=None, name=None, plugs=None,
                 cfg=None):
        self.comp = None
        self.comp_class = class_
        if cfg is None:
            cfg = {}
        self.cfg = cfg
        self.auto_link = True
        self.debug_msgs = []

        self.sync = None
        self.sync_master = None

        if ComponentWrapper._registry is None:
            ComponentWrapper._registry = registry.getRegistry()

        cfg['type'] = type_
        reg = ComponentWrapper._registry.getComponent(type_)

        if not 'source' in cfg:
            cfg['source'] = []

        if not 'eater' in cfg:
            cfg['eater'] = dict([(e.getName(), []) for e in reg.getEaters()
                                 if e.getRequired()])

        if not 'feed' in cfg:
            cfg['feed'] = reg.getFeeders()[:]

        if plugs is not None:
            cfg['plugs'] = plugs
        if not 'plugs' in cfg:
            cfg['plugs'] = dict([(s, []) for s in reg.getSockets()])

        if name:
            cfg['name'] = name
        if not 'name' in cfg:
            cfg['name'] = ComponentWrapper.get_unique_name()
        self.name = cfg['name']

        if not 'parent' in cfg:
            cfg['parent'] = 'default'

        if not 'avatarId' in cfg:
            cfg['avatarId'] = common.componentId(cfg['parent'], self.name)

        if props is not None:
            cfg['properties'] = props
        if not 'properties' in cfg:
            cfg['properties'] = {}

        if not 'clock-master' in cfg:
            cfg['clock-master'] = None

        self.sync_master = cfg['clock-master']

        if reg.getNeedsSynchronization():
            self.sync = reg.getClockPriority()

    def __repr__(self):
        return '%s(%r, %r)' % (self.__class__.__name__,
                               self.comp_class.__name__, self.cfg)

    def get_unique_name(cls, prefix='cmp-'):
        name, cls._u_name_cnt = ('%s%d' % (prefix, cls._u_name_cnt),
                                 cls._u_name_cnt + 1)
        return name
    get_unique_name = classmethod(get_unique_name)

    def instantiate(self):
        # Define a successful instantiation as one that makes a
        # component fire it's setup_completed() method and an
        # unsuccessful as one that makes it sad.
        # We need to hijack the component's setup_completed() and
        # setMood() methods with this bit of ugliness.
        d = defer.Deferred()

        cls = self.comp_class

        self.debug('Dynamically creating a subclass of %r', cls)

        class klass(cls):

            def setup_completed(self):
                # call superclass
                cls.setup_completed(self)
                # fire the deferred returned from instantiate()
                d.callback(self)

            def setMood(self, mood):
                self.debug('hijacked setMood %r on component %r', mood, self)
                current = self.state.get('mood')
                # call superclass
                cls.setMood(self, mood)

                if (current != moods.sad.value
                    and mood.value == moods.sad.value):
                    # The component went sad and it wasn't sad before,
                    # fire the deferred returned from instantiate()
                    d.errback(ComponentSad())

        self.comp = klass(self.cfg)

        self.debug('instantiate:: %r' % self.comp.state)

        def append(instance, key, value):
            self.debug('append %r: %r' % (value.level, value))
            if key == 'messages':
                if value.debug:
                    self.debug('proxied state debug:: %r' % value.debug)
                    self.debug_msgs.append(value.debug)
            flavors.StateCacheable.append(instance, key, value)
        self.comp.state.append = new.instancemethod(append, self.comp.state)
        return d

    def wait_for_mood(self, mood):
        if self.comp.state.get('mood') == mood.value:
            return defer.succeed(mood)

        prev = self.comp.state.set
        d = defer.Deferred()

        def set(key, value):
            self.debug('set %r: %r', key, value)
            prev(key, value)
            if key == 'mood' and value == mood.value:
                d.callback(mood)
        self.comp.state.set = set
        return d

    def feed(self, sink_comp, links=None):
        if links is None:
            links = [('default', 'default')]
        for feeder, eater in links:
            if feeder not in self.cfg['feed']:
                raise ComponentTestException('Invalid feeder specified: %r' %
                                             feeder)
            sink_comp.add_feeder(self, '%s:%s' % (self.name, feeder), eater)

    def add_feeder(self, src_comp, feeder_name, eater):
        self.cfg['source'].append(feeder_name)
        # To fully mimic the behavior of the core, we reproduce its
        # unspecified behavior.
        alias = eater
        while alias in [x[1] for x in self.cfg['eater'].setdefault(eater, [])]:
            alias += '-bis'
        self.cfg['eater'][eater].append((feeder_name, alias))
        self.auto_link = False

    def feedToFD(self, feedName, fd, eaterId=None):
        self.debug('feedToFD(feedName=%s, %d (%s))' % (feedName, fd, eaterId))
        return self.comp.feedToFD(feedName, fd, os.close, eaterId)

    def eatFromFD(self, eaterAlias, feedId, fd):
        self.debug('eatFromFD(eaterAlias=%s, feedId=%s, %d)',
                   eaterAlias, feedId, fd)
        return self.comp.eatFromFD(eaterAlias, feedId, fd)

    def set_master_clock(self, ip, port, base_time):
        self.debug('set_master_clock(%s, %d, %d)', ip, port, base_time)
        return self.comp.set_master_clock(ip, port, base_time)

    def stop(self):
        self.debug('stop()')
        if self.comp:
            return self.comp.stop()
        return defer.succeed(None)


class ComponentTestHelper(object, log.Loggable):
    logCategory = 'comptest-helper'

    guard_timeout = 60.0
    guard_delay = 0.5
    start_delay = None

    def __init__(self):
        self._comps = []
        self._byname = {}
        self._master = None

    def set_flow(self, comp_chain, auto_link=True):
        if len(comp_chain) == 0:
            return

        self._comps = comp_chain

        if auto_link:
            for c_src, c_sink in zip(comp_chain[:-1], comp_chain[1:]):
                if c_sink.auto_link:
                    c_src.feed(c_sink)

        masters = [c for c in self._comps if c.sync_master is not None]
        need_sync = sorted([c for c in self._comps if c.sync is not None],
                           key=(lambda e: e.sync), reverse=True)

        if need_sync:
            if masters:
                master = masters[0]
            else:
                master = need_sync[0]

            master.sync = None # ...? :/
            self._master = master

            master = master.cfg['avatarId']
            for c in need_sync:
                c.cfg['clock-master'] = master
        elif masters:
            for c in masters:
                c.cfg['clock-master'] = None

        for c in self._comps:
            self._byname[c.name] = c
            c.log('updated config for %r: %r' % (c, c.cfg))

    def _make_pipes(self):
        fds = {}

        def feed_starter(c, feed_name, w_fd, feed_id):

            def _feed_starter():
                self.debug('_feed_starter: %r, %r' % (feed_name, feed_id))
                return c.feedToFD(feed_name, w_fd, eaterId=feed_id)
            return _feed_starter
        for c in self._comps:
            eaters = c.cfg['eater']
            for eater_id in eaters:
                for src, alias in eaters[eater_id]:
                    e_name, e_feed = src.split(':')
                    self.debug('creating pipe: %r, %r, %r' %
                               (src, e_feed, eater_id))
                    r_fd, w_fd = os.pipe()
                    fds[src] = (r_fd, feed_starter(self._byname[e_name],
                                                   e_feed, w_fd, eater_id))
        self._fds = fds

    def start_flow(self):
        delay = self.start_delay

        def all_ready_p(results):
            self.debug('** 1: all_ready_p: %r' % results)
            pass

        def setup_failed(failure):
            self.info('*! 1: setup_failed: %r' % (failure, ))
            failure.trap(defer.FirstError)
            return failure.value.subFailure

        def start_master_clock(_):
            self.debug('** 2: start_master_clock: %r (%r)' % (_, self._master))
            if self._master is not None:
                self.debug('About to ask to provide_master_clock()...')
                d = self._master.comp.provide_master_clock(7600 - 1) # ...hack?

                def _passthrough_debug(_res):
                    self.debug('After provide_master_clock() : %r' % (_res, ))
                    return _res
                d.addCallback(_passthrough_debug)
                return d
            return None

        def add_delay(value):
            self.debug('** 3: add_delay: %r, %r' % (delay, value))
            if delay:
                return delayed_d(delay, value)
            return defer.succeed(value)

        def do_start(clocking, c):
            self.debug('** 4: do_start_cb: %r, %r' % (clocking, c))
            for feeds in c.cfg['eater'].values():
                for feedId, eaterAlias in feeds:
                    r_fd, feed_starter = self._fds[feedId]
                    c.eatFromFD(eaterAlias, feedId, r_fd)
                    feed_starter()
            if clocking and c.sync:
                ip, port, base_time = clocking
                c.set_master_clock(ip, port, base_time)

            # we know that the component is already happy, so just
            # pass the clocking to the next component
            return defer.succeed(clocking)

        def do_stop(failure):
            self.debug('** X: do_stop: %r' % failure)
            rcomps = self._comps[:]
            rcomps.reverse()
            for c in rcomps:
                c.stop()
            return failure

        self._make_pipes()

        self.debug('About to start the flow...')
        # P(ossible)TODO: make it report setup failures in all the
        # components, not only in the first to fail...?
        d = defer.DeferredList([c.instantiate() for c in self._comps],
                               fireOnOneErrback=1, consumeErrors=1)
        d.addCallbacks(all_ready_p, setup_failed)
        d.addCallback(start_master_clock)
        for c in self._comps:
            d.addCallback(add_delay)
            d.addCallback(do_start, c)
        d.addErrback(do_stop)
        return d

    def stop_flow(self):
        rcomps = self._comps[:]
        rcomps.reverse()
        d = defer.DeferredList([c.stop() for c in rcomps],
                               fireOnOneErrback=1, consumeErrors=1)

        def stop_flow_report(results):
            self.debug('stop_flow_report: %r' % (results, ))
            return results

        def stop_flow_failed(failure):
            self.info('stop_flow_failed: %r' % (failure, ))
            failure.trap(defer.FirstError)
            self.info('stop_flow_failed! %r' % (failure.value.subFailure, ))
            return failure.value.subFailure
        d.addCallbacks(stop_flow_report, stop_flow_failed)
        return d

    def run_flow(self, duration, tasks=None,
                 start_d=None, start_flow=True, stop_flow=True):

        self.debug('run_flow: tasks: %r' % (tasks, ))
        flow_d = start_d

        if tasks is None:
            tasks = []

        if flow_d is None:
            if start_flow:
                flow_d = self.start_flow()
            else:
                flow_d = defer.succeed(True)

        flow_started_finished = [False, False]

        guard_d = None
        timeout_d = defer.Deferred()
        stop_d = defer.Deferred()
        stop_timeout_d = defer.Deferred()
        chained_d = None

        callids = [None, None, None] # callLater ids: stop_d,
                                     # timeout_d, fire_chained

        if tasks:
            # if have tasks, run simultaneously with the main timer deferred
            chained_d = defer.DeferredList([stop_d] + tasks,
                                           fireOnOneErrback=1, consumeErrors=1)

            def chained_failed(failure):
                self.info('chained_failed: %r' % (failure, ))
                failure.trap(defer.FirstError)
                return failure.value.subFailure
            chained_d.addErrback(chained_failed)
        else:
            # otherwise, just idle...
            chained_d = stop_d

        def start_complete(result):
            self.debug('start_complete: %r' % (result, ))
            flow_started_finished[0] = True
            callids[0] = reactor.callLater(duration, stop_d.callback, None)
            if tasks:

                def _fire_chained():
                    callids[2] = None
                    for t in tasks:
                        try:
                            t.callback(result)
                        except defer.AlreadyCalledError:
                            pass
                callids[2] = reactor.callLater(0, _fire_chained)
            return chained_d

        def flow_complete(result):
            self.debug('flow_complete: %r' % (result, ))
            flow_started_finished[1] = True
            return result

        def flow_timed_out():
            self.debug('flow_timed_out!')
            if not flow_started_finished[0]:
                timeout_d.errback(StartTimeout('flow start timed out'))
            elif not flow_started_finished[1]:
                timeout_d.errback(FlowTimeout('flow run timed out'))
            else:
                stop_timeout_d.errback(StopTimeout('flow stop timed out'))

        def clean_calls(result):
            self.debug('clean_calls: %r' % (result, ))
            for i, cid in enumerate(callids):
                if cid is not None:
                    if cid.active():
                        cid.cancel()
                    callids[i] = None
            return result

        flow_d.addCallback(start_complete)
        flow_d.addCallback(flow_complete)

        guard_d = defer.DeferredList([flow_d, timeout_d], consumeErrors=1,
                                     fireOnOneErrback=1, fireOnOneCallback=1)

        def guard_failed(failure):
            self.info('guard_failed: %r' % (failure, ))
            failure.trap(defer.FirstError)
            return failure.value.subFailure
        if stop_flow:

            def _force_stop_flow(result):
                self.debug('_force_stop_flow: %r' % (result, ))
                d = defer.DeferredList([self.stop_flow(), stop_timeout_d],
                                       fireOnOneErrback=1, fireOnOneCallback=1,
                                       consumeErrors=1)

                def _return_orig_result(stop_result):
                    if isinstance(result, failure.Failure):
                        # always return the run's failure first
                        # what do I return if both the run and stop failed?
                        self.debug('_return_orig[R]: %r' % (result, ))
                        return result
                    elif isinstance(stop_result, failure.Failure):
                        # return failure from stop
                        self.debug('_return_orig[S]: %r' % (stop_result, ))
                        return stop_result
                    return result

                def force_stop_failed(failure):
                    self.info('force_stop_failed: %r' % (failure, ))
                    failure.trap(defer.FirstError)
                    return failure.value.subFailure
                d.addCallbacks(lambda r: r[0], force_stop_failed)
                d.addBoth(_return_orig_result)
                return d
            guard_d.addBoth(_force_stop_flow)

        guard_d.addErrback(guard_failed)
        guard_d.addBoth(clean_calls)

        callids[1] = reactor.callLater(self.guard_timeout, flow_timed_out)
        return guard_d


def cleanup_reactor(force=False):
    log.debug('comptest', 'running cleanup_reactor...')
    delayed = reactor.getDelayedCalls()
    for dc in delayed:
        dc.cancel()
    # the rest is taken from twisted trial...
    sels = reactor.removeAll()
    if sels:
        log.info('comptest', 'leftover selectables...: %r %r' %
                 (sels, reactor.waker))
        for sel in sels:
            if interfaces.IProcessTransport.providedBy(sel):
                sel.signalProcess('KILL')


def pipeline_src(pipelinestr='fakesrc datarate=1024 is-live=true ! '
                 'video/x-raw-rgb,framerate=(fraction)8/1,width=32,height=24'):
    fs_name = ComponentWrapper.get_unique_name('ppln-src-')

    return ComponentWrapper('pipeline-producer', Producer, name=fs_name,
                            props={'pipeline': pipelinestr})


def pipeline_cnv(pipelinestr='identity'):
    fs_name = ComponentWrapper.get_unique_name('ppln-cnv-')

    return ComponentWrapper('pipeline-converter', Converter, name=fs_name,
                            props={'pipeline': pipelinestr})
