# -*- Mode: Python; test-case-name: flumotion.test.test_common_pygobject -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

from twisted.trial import unittest
from twisted.internet import reactor

import common

import gobject
import gtk

from flumotion.common import pygobject, errors

class SetProperty(unittest.TestCase):
    def testButton(self):
        b = gtk.Button()

        # string
        pygobject.gobject_set_property(b, 'name', 'button')
        self.assertRaises(errors.PropertyError,
            pygobject.gobject_set_property, b, 'doesnotexist', 'somevalue')

        # int
        pygobject.gobject_set_property(b, 'width-request', 1)
        self.assertRaises(errors.PropertyError,
            pygobject.gobject_set_property, b, 'width-request', 'notanint')

        # boolean
        pygobject.gobject_set_property(b, 'can-focus', 'True')
        self.assertEquals(b.get_property('can-focus'), True)
        pygobject.gobject_set_property(b, 'can-focus', 'False')
        self.assertEquals(b.get_property('can-focus'), False)
        pygobject.gobject_set_property(b, 'can-focus', 'something')
        self.assertEquals(b.get_property('can-focus'), True)
        pygobject.gobject_set_property(b, 'can-focus', [])
        self.assertEquals(b.get_property('can-focus'), False)
