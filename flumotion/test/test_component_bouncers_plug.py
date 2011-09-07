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

from flumotion.common import testsuite

from twisted.internet import defer

from flumotion.component.bouncers import plug


class TrivialBouncerTest(testsuite.TestCase):

    skip = 'Needs rewrite to use the changed bouncer plugs interface'

    def setUp(self):
        args = {'socket': 'flumotion.component.bouncers.plug.BouncerPlug',
                'type': 'bouncer-trivial',
                'properties': {}}
        self.obj = plug.BouncerTrivialPlug(args)
        self.medium = bouncertest.FakeMedium()
        self.obj.setMedium(self.medium)
        d = defer.maybeDeferred(self.obj.start, None)
        d.addCallback(lambda _: bouncertest.TrivialBouncerTest.setUp(self))
        return d

    def tearDown(self):
        d = defer.maybeDeferred(self.obj.stop, None)
        d.addCallback(lambda _: bouncertest.TrivialBouncerTest.tearDown(self))
        return d

    def testFake(self):
        pass
