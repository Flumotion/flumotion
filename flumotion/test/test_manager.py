# -*- Mode: Python; test-case-name: flumotion.test.test_manager -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/test/test_manager.py: regression test for flumotion.manager
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

from flumotion.manager import component, manager
from flumotion.utils import log

class FakeComponentAvatar(log.Loggable):
    ### since we fake out componentavatar, eaters need to be specified fully
    ### for the tests, ie sourceComponentName:feedName
    def __init__(self, name='fake', eaters=[], port=-1, listen_host='listen-host'):
        self.name = name
        self.eaters = eaters
        self.port = port
        self.listen_host = listen_host
        
    def getFeeders(self):
        return [self.name + ':default']

    def getFeedPort(self, feedName):
        return self.port

    def getEaters(self):
        return self.eaters
    
    def getListenHost(self):
        return self.listen_host

    def getListenPort(self, *args):
        return self.port
    
    def getTransportPeer(self):
        return 0, '127.0.0.1', 0

    def getName(self):
        return self.name

class TestComponentHeaven(unittest.TestCase):
    def setUp(self):
        self.heaven = component.ComponentHeaven(manager.Vishnu())

    def testCreateAvatar(self):
        p = self.heaven.createAvatar('foo-bar-baz')
        assert isinstance(p, component.ComponentAvatar)

        #self.assertRaises(AssertionError,
        #                  self.heaven.createAvatar, 'does-not-exist')

    def testIsLocalComponent(self):
        a = FakeComponentAvatar()
        self.heaven._addComponentAvatar(a)
        assert self.heaven.isLocalComponent(a)
        
    def testIsStarted(self):
        a = self.heaven.createAvatar('prod')
        assert not self.heaven.isComponentStarted('prod')
        a.started = True # XXX: Use heaven.componentStart
        assert self.heaven.isComponentStarted('prod')

    def testGetComponent(self):
        a = self.heaven.createAvatar('prod')
        assert self.heaven.getComponent('prod') == a

    def testHasComponent(self):
        a = self.heaven.createAvatar('prod')
        assert self.heaven.hasComponent('prod')
        self.heaven.removeComponent(a)
        assert not self.heaven.hasComponent('prod')
        self.assertRaises(KeyError, self.heaven.removeComponent, a)
        
    def testAddComponent(self):
        a = FakeComponentAvatar('fake')
        self.heaven._addComponentAvatar(a)
        assert self.heaven.hasComponent('fake')
        self.assertRaises(KeyError, self.heaven._addComponentAvatar, a)
        
    def testRemoveComponent(self):
        assert not self.heaven.hasComponent('fake')
        a = FakeComponentAvatar('fake')
        self.assertRaises(KeyError, self.heaven.removeComponent, a)
        self.heaven._addComponentAvatar(a)
        assert self.heaven.hasComponent('fake')
        self.heaven.removeComponent(a)
        assert not self.heaven.hasComponent('fake')
        self.assertRaises(KeyError, self.heaven.removeComponent, a)

    def testComponentEatersEmpty(self):
        a = FakeComponentAvatar('fake')
        self.heaven._addComponentAvatar(a)
        assert self.heaven._getComponentEatersData(a) == []
        
    def testComponentsEaters(self):
        a = FakeComponentAvatar('foo', ['bar:default', 'baz:default'])
        self.heaven._addComponentAvatar(a)
        a2 = FakeComponentAvatar('bar', port=1000, listen_host='bar-host')
        self.heaven._addComponentAvatar(a2)
        a3 = FakeComponentAvatar('baz', port=1001, listen_host='baz-host')
        self.heaven._addComponentAvatar(a3)

        self.heaven.feeder_set.addFeeders(a2)
        self.heaven.feeder_set.addFeeders(a3)
        
        eaters = self.heaven._getComponentEatersData(a)
        assert len(eaters) == 2
        assert ('bar:default', 'bar-host', 1000) in eaters
        assert ('baz:default', 'baz-host', 1001) in eaters        

if __name__ == '__main__':
     unittest.main()
