# -*- Mode: Python; test-case-name: flumotion.test.test_enum -*-
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

from twisted.spread import jelly

from flumotion.common import enum
from flumotion.common import testsuite


class TestEnum(testsuite.TestCase):

    def testEnumSimple(self):
        en = enum.EnumClass('TestEnum')
        self.assertEquals(en.__name__, 'TestEnum')
        self.assertEquals(len(en), 0)
        self.assertRaises(KeyError, en.get, 0)
        self.assertRaises(StopIteration, en.__getitem__, 0)

    def testEnumValues(self):
        en = enum.EnumClass('TestEnum', ('Zero', 'One', 'Two'))
        self.assertEquals(en.__name__, 'TestEnum')
        self.assertEquals(len(en), 3)
        self.assertEquals(en.get(0).name, 'Zero')
        self.assertEquals(en.get(1).name, 'One')
        self.assertEquals(en.get(2).name, 'Two')
        self.assertRaises(StopIteration, en.__getitem__, 3)

    def testEnumValuesWithRepr(self):
        en = enum.EnumClass('TestEnum', ('Zero', 'One', 'Two'),
                               ('This is the first',
                                'This is the second',
                                'This is the third'))
        self.assertEquals(len(en), 3)
        self.failUnless(issubclass(en, enum.Enum))
        self.failUnless(hasattr(en, 'Zero'))
        self.failUnless(hasattr(en, 'One'))
        self.failUnless(hasattr(en, 'Two'))

        e0 = en.Zero
        e1 = en.One
        e2 = en.Two
        self.assertEquals(e0.value, 0)
        self.assertEquals(e1.value, 1)
        self.assertEquals(e2.value, 2)
        self.assertEquals(e0.name, 'Zero')
        self.assertEquals(e1.name, 'One')
        self.assertEquals(e2.name, 'Two')
        self.assertEquals(e0.nick, 'This is the first')
        self.assertEquals(e1.nick, 'This is the second')
        self.assertEquals(e2.nick, 'This is the third')

        self.assertEquals(en.get(0), e0)
        self.assertEquals(en.get(1), e1)
        self.assertEquals(en.get(2), e2)

        self.assertEquals(tuple(en), (e0, e1, e2))

    def testEnumValuesCmp(self):
        FooType = enum.EnumClass('FooType', ('Foo', 'Foobie'))
        BarType = enum.EnumClass('BarType', ('Bar', 'Barrie'))

        # FooType with FooType
        self.assertEquals(FooType.Foo, FooType.Foo)
        self.assertNotEquals(FooType.Foo, FooType.Foobie)
        self.assertNotEquals(FooType.Foobie, FooType.Foo)
        self.assertEquals(FooType.Foobie, FooType.Foobie)

        # BarType with BarType
        self.assertEquals(BarType.Bar, BarType.Bar)
        self.assertNotEquals(BarType.Bar, BarType.Barrie)
        self.assertNotEquals(BarType.Barrie, BarType.Bar)
        self.assertEquals(BarType.Barrie, BarType.Barrie)

        # FooType with BarType
        self.assertNotEquals(FooType.Foo, BarType.Bar)
        self.assertNotEquals(FooType.Foo, BarType.Barrie)
        self.assertNotEquals(FooType.Foobie, BarType.Bar)
        self.assertNotEquals(FooType.Foobie, BarType.Barrie)

        # BarType with FooType
        self.assertNotEquals(BarType.Bar, FooType.Foo)
        self.assertNotEquals(BarType.Bar, FooType.Foobie)
        self.assertNotEquals(BarType.Barrie, FooType.Foo)
        self.assertNotEquals(BarType.Barrie, FooType.Foobie)

    def testEnumError(self):
        # nicks of incorrect length
        self.assertRaises(TypeError, enum.EnumClass, 'Foo',
                          ('a', 'b'), ('c', ))
        self.assertRaises(TypeError, enum.EnumClass, 'Bar',
                          ('a', ), ('b', 'c'))
        # extra of invalid type
        self.assertRaises(TypeError, enum.EnumClass, 'Baz',
                          ('a', 'b'), ('b', 'c'), extra=None)
        self.assertRaises(TypeError, enum.EnumClass, 'Boz',
                          ('a', 'b'), ('b', 'c'), extra=('e', ))

    def testEnumSet(self):
        FooType = enum.EnumClass('FooType', ('Foo', 'Bar'))
        FooType.set(0, FooType(3, 'Baz'))

    def testRepr(self):
        a = enum.EnumClass('FooType', ('Foo', 'Bar'))
        self.failUnless(repr(a.Foo))
        self.failUnless(isinstance(repr(a.Foo), str))

    def testJelly(self):
        a = enum.EnumClass('FooType', ('Foo', 'Bar'))
        self.assertEquals(jelly.unjelly(jelly.jelly(a.Foo)), a.Foo)
        self.assertEquals(jelly.unjelly(jelly.jelly(a.Bar)), a.Bar)
        self.assertNotEquals(jelly.unjelly(jelly.jelly(a.Foo)), a.Bar)
        self.assertNotEquals(jelly.unjelly(jelly.jelly(a.Bar)), a.Foo)
