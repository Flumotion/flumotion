# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2007 Fluendo, S.L. (www.fluendo.com).
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

from flumotion.component.bouncers import component
from flumotion.test import bouncertest


class FakeBouncerMedium(bouncertest.FakeMedium, component.BouncerMedium):

    def __init__(self):
        pass


class TrivialBouncerTest(bouncertest.TrivialBouncerTest):

    def setUp(self):
        plugs = {component.BOUNCER_SOCKET:
                 [{'socket': component.BOUNCER_SOCKET,
                   'type': 'trivial-bouncer-plug',
                   'properties': {},
                   'entries': {'default':
                               {'module-name':
                                'flumotion.component.bouncers.plug',
                                'function-name':
                                'TrivialBouncerPlug'}}}]}
        self.obj = component.Bouncer({'name': 'fake',
                                      'avatarId': '/default/fake',
                                      'plugs': plugs,
                                      'properties': {}})

        self.medium = FakeBouncerMedium()
        self.obj.setMedium(self.medium)
        d = self.obj.waitForHappy()
        d.addCallback(lambda _: bouncertest.TrivialBouncerTest.setUp(self))
        return d

    def tearDown(self):
        d = self.obj.stop()
        d.addCallback(lambda _: bouncertest.TrivialBouncerTest.tearDown(self))
        return d

    def setKeycardExpireInterval(self, interval):
        # can be overridden
        self.obj.plug._expirer.timeout = interval
