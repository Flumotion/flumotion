# -*- Mode: Python; test-case-name: flumotion.test.test_wizard_models -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2008 Fluendo, S.L. (www.fluendo.com).
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

import unittest

from flumotion.common import testsuite
from flumotion.common.errors import ComponentError
from flumotion.wizard.models import Flow, Component, Properties

__version__ = "$Rev$"


class TestFlow(testsuite.TestCase):
    def setUp(self):
        self.flow = Flow()

    def testAddComponent(self):
        self.assertRaises(TypeError, self.flow.addComponent, None)

        component = Component()
        self.flow.addComponent(component)
        self.assertRaises(ComponentError, self.flow.addComponent, component)

        self.assertEqual(component.name, "component")

        component2 = Component()
        self.flow.addComponent(component2)
        self.assertEqual(component2.name, "component-2")

    def testRemoveComponent(self):
        self.assertRaises(TypeError, self.flow.removeComponent, None)

        component = Component()
        self.assertRaises(ComponentError, self.flow.removeComponent, component)

        self.flow.addComponent(component)
        self.failUnless(component.name)

        self.flow.removeComponent(component)
        self.failIf(component.name)

    def testContains(self):
        component = Component()
        self.failIf(component in self.flow)
        self.flow.addComponent(component)
        self.failUnless(component in self.flow)
        self.flow.removeComponent(component)
        self.failIf(component in self.flow)

    def testIter(self):
        component = Component()
        self.assertEquals(list(self.flow), [])
        self.flow.addComponent(component)
        self.assertEquals(list(self.flow), [component])

        component2 = Component()
        self.flow.addComponent(component2)

        self.assertEquals(list(self.flow), [component, component2])
        for component in list(self.flow):
            self.flow.removeComponent(component)
        self.assertEquals(list(self.flow), [])


class TestComponent(testsuite.TestCase):
    def setUp(self):
        self.component = Component()

class TestProperties(testsuite.TestCase):
    def setUp(self):
        self.props = Properties()

    def testInsertItem(self):
        self.props['foo'] = 10

        self.failUnless(self.props)

        self.failUnless(hasattr(self.props, 'foo'))
        self.assertEquals(self.props.foo, 10)

        self.failUnless('foo' in self.props)
        self.assertEquals(self.props['foo'], 10)

    def testInsertAttribute(self):
        self.props.foo = 10

        self.failUnless(self.props)

        self.failUnless(hasattr(self.props, 'foo'))
        self.assertEquals(self.props.foo, 10)

        self.failUnless('foo' in self.props)
        self.assertEquals(self.props['foo'], 10)

    def testDeleteItem(self):
        self.props.foo = 10

        del self.props['foo']

        self.failIf(hasattr(self.props, 'foo'))
        self.failIf('foo' in self.props)

    def testDeleteAttribute(self):
        self.props.foo = 10

        del self.props.foo

        self.failIf(hasattr(self.props, 'foo'))
        self.failIf('foo' in self.props)

    def testInsertInvalid(self):
        self.assertRaises(AttributeError,
                          self.props.__setattr__, 'update', 10)
        self.failIf(self.props)

        self.assertRaises(AttributeError,
                          self.props.__setitem__, 'update', 10)
        self.failIf(self.props)

if __name__ == "__main__":
    unittest.main()
