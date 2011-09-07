# -*- Mode: Python; test-case-name: flumotion.test.test_wizard_models -*-
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

import unittest

from flumotion.common import testsuite
from flumotion.admin.assistant.models import Component, Properties


class TestComponent(testsuite.TestCase):

    def setUp(self):
        self.component = Component()


class TestProperties(testsuite.TestCase):

    def setUp(self):
        self.props = Properties()

    def testSetItem(self):
        self.props['foo'] = 10

        self.failUnless(self.props)

        self.failUnless(hasattr(self.props, 'foo'))
        self.assertEquals(self.props.foo, 10)

        self.failUnless('foo' in self.props)
        self.assertEquals(self.props['foo'], 10)

    def testSetItemUnderscore(self):
        self.props['foo-bar'] = 10

        self.failUnless(self.props)

        self.failUnless(hasattr(self.props, 'foo_bar'))
        self.assertEquals(self.props.foo_bar, 10)

        self.failUnless('foo-bar' in self.props)
        self.failUnless('foo_bar' in self.props)
        self.assertEquals(self.props['foo-bar'], 10)

    def testSetAttribute(self):
        self.props.foo = 10

        self.failUnless(self.props)

        self.failUnless(hasattr(self.props, 'foo'))
        self.assertEquals(self.props.foo, 10)

        self.failUnless('foo' in self.props)
        self.assertEquals(self.props['foo'], 10)

    def testSetAttributeUnderscore(self):
        self.props.foo_bar = 10

        self.failUnless(self.props)

        self.failUnless(hasattr(self.props, 'foo_bar'))
        self.assertEquals(self.props.foo_bar, 10)

        self.failUnless('foo-bar' in self.props)
        self.failUnless('foo_bar' in self.props)
        self.assertEquals(self.props['foo-bar'], 10)

    def testDeleteItem(self):
        self.props.foo = 10

        del self.props['foo']

        self.failIf(hasattr(self.props, 'foo'))
        self.failIf('foo' in self.props)

    def testDeleteItemUnderscore(self):
        self.props.foo_bar = 10

        del self.props['foo-bar']

        self.failIf(hasattr(self.props, 'foo_bar'))
        self.failIf('foo-bar' in self.props)

    def testDeleteAttribute(self):
        self.props.foo = 10

        del self.props.foo

        self.failIf(hasattr(self.props, 'foo'))
        self.failIf('foo' in self.props)

    def testDeleteAttributeUnderscore(self):
        self.props.foo_bar = 10
        del self.props.foo_bar

        self.failIf(hasattr(self.props, 'foo_bar'))
        self.failIf('foo-bar' in self.props)

    def testSetInvalid(self):
        self.assertRaises(AttributeError,
                          self.props.__setattr__, 'update', 10)
        self.failIf(self.props)

        self.assertRaises(AttributeError,
                          self.props.__setitem__, 'update', 10)
        self.failIf(self.props)

    def testContains(self):
        self.props.foo_bar = 10
        self.failUnless('foo-bar' in self.props)
        self.failUnless('foo_bar' in self.props)
        del self.props.foo_bar
        self.failIf('foo-bar' in self.props)
        self.failIf('foo_bar' in self.props)

if __name__ == "__main__":
    unittest.main()
