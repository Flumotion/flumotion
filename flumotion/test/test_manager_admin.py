# -*- Mode: Python; test-case-name: flumotion.test.test_manager_admin -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/test/test_manager_admin.py:
# regression test for flumotion.manager.admin
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

import common
from twisted.trial import unittest

from flumotion.manager import admin, component

# our test for twisted's challenger
# this is done for comparison with our challenger
class FakeVishnu:
    def __init__(self):
        self.componentHeaven = FakeHeaven(self)
        self.workerHeaven = FakeHeaven(self)

class FakeHeaven:
    def __init__(self, vishnu):
        self.vishnu = vishnu

class TestComponentView(unittest.TestCase):
    def setUp(self):
        vishnu = FakeVishnu()
        self.heaven = FakeHeaven(vishnu)

    def test__repr__(self):
        componentAvatar = component.ComponentAvatar(self.heaven, 'username')
        view = admin.ComponentView(componentAvatar)
        "%r" % view

    def test__cmp__(self):
        componentAvatar1 = component.ComponentAvatar(self.heaven, 'username1')
        view1 = admin.ComponentView(componentAvatar1)
        componentAvatar2 = component.ComponentAvatar(self.heaven, 'username2')
        view2 = admin.ComponentView(componentAvatar2)
        view1 is view1
        view1 is not view2

class TestAdminAvatar(unittest.TestCase):
    def setUp(self):
        vishnu = FakeVishnu()
        self.heaven = FakeHeaven(vishnu)

    def testHasRemoteReference(self):
        avatar = admin.AdminAvatar(self.heaven, 'admin')
        avatar.hasRemoteReference()

if __name__ == '__main__':
     unittest.main()
