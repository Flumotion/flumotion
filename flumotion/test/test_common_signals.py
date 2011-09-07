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

from flumotion.common import signals
from flumotion.common import testsuite


class TestObject(signals.SignalMixin):
    __signals__ = ('foo', 'bar')


class TestSignalMixin(testsuite.TestCase):

    def testEmitSelf(self):
        o = TestObject()

        emissions = []

        def trackEmission(*args, **kwargs):
            emissions.append((args[-1], args[:-1], kwargs))

        o.connect('foo', trackEmission, 'foo')
        o.emit('foo')

        self.assertEquals(emissions, [('foo', (o, ), {})])

    def testMixin(self):
        o = TestObject()

        o.emit('foo')
        o.emit('bar')

        self.assertRaises(ValueError, o.emit, 'qux')

        emissions = []

        def trackEmission(*args, **kwargs):
            emissions.append((args[-1], args[:-1], kwargs))

        o.connect('foo', trackEmission, 'foo')
        o.connect('bar', trackEmission, 'bar', baz='qux')

        o.emit('foo')
        self.assertEquals(emissions, [('foo', (o, ), {})])
        o.emit('foo', 1)
        self.assertEquals(emissions, [('foo', (o, ), {}),
                                      ('foo', (o, 1, ), {})])
        o.emit('bar', 'xyzzy')
        self.assertEquals(emissions, [('foo', (o, ), {}),
                                      ('foo', (o, 1, ), {}),
                                      ('bar', (o, 'xyzzy', ), {'baz':'qux'})])

    def testDisconnect(self):
        o = TestObject()

        sid = o.connect('foo', self.fail)
        o.disconnect(sid)
        o.emit('foo')

    def testDisconnectByFunc(self):
        o = TestObject()

        o.connect('foo', self.fail)
        o.disconnectByFunction(self.fail)
        o.emit('foo')
