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

from twisted.python import failure
from twisted.internet import defer, reactor, interfaces, gtk2reactor
from twisted.web import client, error

from flumotion.common import testsuite
from flumotion.common import log, errors
from flumotion.common.planet import moods
from flumotion.component.consumers.disker import disker

from flumotion.test import comptest


class PluggableComponentTestCase(comptest.CompTestTestCase):

    def get_plugs(self, socket):
        """Return plug configs for the given socket."""
        return []

    def build_plugs(self, sockets=None):
        if sockets is None:
            sockets = ()
        plugs = dict([(s, self.get_plugs(s)) for s in sockets])
        return plugs


class TestConfig(PluggableComponentTestCase, log.Loggable):

    logCategory = 'disker-test'

    def tearDown(self):
        # we instantiate the component, and it doesn't clean after
        # itself correctly, so we need to manually clean the reactor
        comptest.cleanup_reactor()

    def get_config(self, properties):
        return {'feed': [],
                'name': 'disk-video',
                'parent': 'default',
                'eater': {'default':
                              [('default', 'video-source:video')]},
                'source': ['video-source:video'],
                'avatarId': '/default/disk-video',
                'clock-master': None,
                'plugs':
                    self.build_plugs(['flumotion.component.consumers.'
                                      'disker.disker_plug.DiskerPlug']),
                'type': 'disk-consumer',
                'properties': properties}

    def test_config_minimal(self):
        properties = {'directory': '/tmp'}

        dc = comptest.ComponentWrapper('disk-consumer', disker.Disker,
                                       name='dc',
                                       cfg=self.get_config(properties))
        d = dc.instantiate()
        # actually wait for the component to start up and go hungry
        d.addCallback(lambda _: dc.wait_for_mood(moods.hungry))
        d.addCallback(lambda _: dc.stop())
        return d

    def test_config_rotate_invalid(self):
        properties = {'directory': '/tmp',
                      'rotate-type': 'invalid'}

        dc = comptest.ComponentWrapper('disk-consumer', disker.Disker,
                                       name='dc',
                                       cfg=self.get_config(properties))
        d = dc.instantiate()
        return self.failUnlessFailure(d, comptest.ComponentSad)

    def test_config_rotate_size_no_size(self):
        properties = {'directory': '/tmp',
                      'rotate-type': 'size'}

        dc = comptest.ComponentWrapper('disk-consumer', disker.Disker,
                                       name='dc',
                                       cfg=self.get_config(properties))
        d = dc.instantiate()
        return self.failUnlessFailure(d, comptest.ComponentSad)

    def test_config_rotate_time_no_time(self):
        properties = {'directory': '/tmp',
                      'rotate-type': 'time'}

        dc = comptest.ComponentWrapper('disk-consumer', disker.Disker,
                                       name='dc',
                                       cfg=self.get_config(properties))
        d = dc.instantiate()
        return self.failUnlessFailure(d, comptest.ComponentSad)

    def test_config_rotate_size(self):
        properties = {'directory': '/tmp',
                      'rotate-type': 'size',
                      'size': 16}

        dc = comptest.ComponentWrapper('disk-consumer', disker.Disker,
                                       name='dc',
                                       cfg=self.get_config(properties))
        d = dc.instantiate()
        # don't wait for it to go hungry, be happy with just
        # instantiating correctly
        return d

    def test_config_rotate_time(self):
        properties = {'directory': '/tmp',
                      'rotate-type': 'time',
                      'time': 10}

        dc = comptest.ComponentWrapper('disk-consumer', disker.Disker,
                                       name='dc',
                                       cfg=self.get_config(properties))
        d = dc.instantiate()
        # don't wait for it to go hungry, be happy with just
        # instantiating correctly
        return d


class TestFlow(PluggableComponentTestCase, log.Loggable):

    def setUp(self):
        self.tp = comptest.ComponentTestHelper()
        prod = ('videotestsrc is-live=true ! '
                'video/x-raw-rgb,framerate=(fraction)1/2,width=320,height=240')
        self.s = 'flumotion.component.consumers.disker.disker_plug.DiskerPlug'

        self.prod = comptest.pipeline_src(prod)

    def tearDown(self):
        comptest.cleanup_reactor()

    def test_size_disker_running_and_happy(self):
        properties = {'directory': '/tmp',
                      'rotate-type': 'size',
                      'size': 10,
                      'symlink-to-current-recording': 'current'}

        dc = comptest.ComponentWrapper('disk-consumer', disker.Disker,
                                       name='disk-video', props=properties,
                                       plugs=self.build_plugs([self.s]))

        self.tp.set_flow([self.prod, dc])

        d = self.tp.start_flow()

        # wait for the disker to go happy
        d.addCallback(lambda _: dc.wait_for_mood(moods.happy))
        # let it run for a few seconds
        d.addCallback(lambda _: comptest.delayed_d(30, _))
        # and finally stop the flow
        d.addCallback(lambda _: self.tp.stop_flow())
        return d

    def test_time_disker_running_and_happy(self):
        properties = {'directory': '/tmp',
                      'rotate-type': 'time',
                      'time': 10,
                      'symlink-to-current-recording': 'current'}

        dc = comptest.ComponentWrapper('disk-consumer', disker.Disker,
                                       name='disk-video', props=properties,
                                       plugs=self.build_plugs([self.s]))

        self.tp.set_flow([self.prod, dc])

        d = self.tp.start_flow()

        # wait for the disker to go happy
        d.addCallback(lambda _: dc.wait_for_mood(moods.happy))
        # let it run for a few seconds
        d.addCallback(lambda _: comptest.delayed_d(30, _))
        # and finally stop the flow
        d.addCallback(lambda _: self.tp.stop_flow())
        return d
