# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/test/test_enum.py: enum tests
#
# Flumotion - a streaming media server
# Copyright (C) 2004 Fluendo (www.fluendo.com)

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
# See "LICENSE.GPL" in the source distribution for more information.

# This program is also licensed under the Flumotion license.
# See "LICENSE.Flumotion" in the source distribution for more information.

from twisted.trial import unittest

from flumotion.wizard import enums

class TestEnum(unittest.TestCase):
    def testEnumSimple(self):
        enum = enums.EnumClass('TestEnum')
        assert enum.__name__ == 'TestEnum'
        assert len(enum) == 0
        self.assertRaises(KeyError, enum.get, 0)
        self.assertRaises(StopIteration, enum.__getitem__, 0)

    def testEnumValues(self):
        enum = enums.EnumClass('TestEnum', ('Zero', 'One', 'Two'))
        assert enum.__name__ == 'TestEnum'
        assert len(enum) == 3
        assert enum.get(0).name == 'Zero'
        assert enum.get(1).name == 'One'
        assert enum.get(2).name == 'Two'
        self.assertRaises(StopIteration, enum.__getitem__, 3)
    
    def testEnumValuesWithRepr(self):
        enum = enums.EnumClass('TestEnum', ('Zero', 'One', 'Two'),
                               ('This is the first',
                                'This is the second',
                                'This is the third'))
        assert len(enum) == 3
        assert issubclass(enum, enums.Enum)
        assert hasattr(enum, 'Zero')
        assert hasattr(enum, 'One')
        assert hasattr(enum, 'Two')

        e0 = enum.Zero
        e1 = enum.One
        e2 = enum.Two
        assert e0.value == 0
        assert e1.value == 1
        assert e2.value == 2
        assert e0.name == 'Zero'
        assert e1.name == 'One'
        assert e2.name == 'Two'
        assert e0.nick == 'This is the first'
        assert e1.nick == 'This is the second'
        assert e2.nick == 'This is the third'
        
        assert enum.get(0) == e0
        assert enum.get(1) == e1
        assert enum.get(2) == e2
        
        assert tuple(enum) == (e0, e1, e2)

    def testEnumValuesCmp(self):
        FooType = enums.EnumClass('FooType', ('Foo', 'Foobie'))
        BarType = enums.EnumClass('BarType', ('Bar', 'Barrie'))

        # FooType with FooType
        assert FooType.Foo == FooType.Foo
        assert FooType.Foo != FooType.Foobie
        assert FooType.Foobie != FooType.Foo
        assert FooType.Foobie == FooType.Foobie

        # BarType with BarType
        assert BarType.Bar == BarType.Bar
        assert BarType.Bar != BarType.Barrie
        assert BarType.Barrie != BarType.Bar
        assert BarType.Barrie == BarType.Barrie

        # FooType with BarType
        assert FooType.Foo != BarType.Bar
        assert FooType.Foo != BarType.Barrie
        assert FooType.Foobie != BarType.Bar
        assert FooType.Foobie != BarType.Barrie
        
        # BarType with FooType
        assert BarType.Bar != FooType.Foo
        assert BarType.Bar != FooType.Foobie
        assert BarType.Barrie != FooType.Foo
        assert BarType.Barrie != FooType.Foobie

    def testEnumError(self):
        # nicks of incorrect length
        self.assertRaises(TypeError, enums.EnumClass, 'Foo',
                          ('a', 'b'), ('c',))
        self.assertRaises(TypeError, enums.EnumClass, 'Bar',
                          ('a',), ('b', 'c'))
        # extra of invalid type
        self.assertRaises(TypeError, enums.EnumClass, 'Baz',
                          ('a', 'b'), ('b', 'c'), extra=None)
        self.assertRaises(TypeError, enums.EnumClass, 'Boz',
                          ('a', 'b'), ('b', 'c'), extra=('e',))

    def testEnumSet(self):
        FooType = enums.EnumClass('FooType', ('Foo', 'Bar'))
        FooType.set(0, FooType(3, 'Baz'))

    def testRepr(self):
        a = enums.EnumClass('FooType', ('Foo', 'Bar'))
        assert repr(a.Foo)
        assert isinstance(repr(a.Foo), str)
