# -*- Mode: Python; test-case-name: flumotion.test.test_manager -*-
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

import common

from twisted.trial import unittest

from flumotion.manager import component, manager
from flumotion.common import log

class FakeComponentAvatar(log.Loggable):
    ### since we fake out componentavatar, eaters need to be specified fully
    ### for the tests, ie sourceComponentName:feedName
    def __init__(self, name='fake', eaters=[], port=-1, listen_host='127.0.0.1'):
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
    
    def getClientAddress(self):
        return self.listen_host

    def getListenPort(self, *args):
        return self.port
    
    def getName(self):
        return self.name

    def cleanup(self):
        pass

class TestComponentHeaven(unittest.TestCase):
    def setUp(self):
        self.heaven = component.ComponentHeaven(manager.Vishnu())

    def testCreateAvatar(self):
        p = self.heaven.createAvatar('foo-bar-baz')
        assert isinstance(p, component.ComponentAvatar)

        #self.assertRaises(AssertionError,
        #                  self.heaven.createAvatar, 'does-not-exist')
        p.cleanup()

    def testComponentIsLocal(self):
        a = FakeComponentAvatar()
        self.heaven.avatars['test'] = a
        assert self.heaven._componentIsLocal(a)
        
    def testGetComponent(self):
        a = self.heaven.createAvatar('prod')
        assert self.heaven.getComponent('prod') == a
        a.cleanup()

    def testHasComponent(self):
        a = self.heaven.createAvatar('prod')
        assert self.heaven.hasComponent('prod')
        self.heaven.removeComponent(a)
        assert not self.heaven.hasComponent('prod')
        self.assertRaises(KeyError, self.heaven.removeComponent, a)
        
    def testRemoveComponent(self):
        assert not self.heaven.hasComponent('fake')
        a = FakeComponentAvatar('fake')
        self.assertRaises(KeyError, self.heaven.removeComponent, a)
        self.heaven.avatars['fake'] = a
        assert self.heaven.hasComponent('fake')
        self.heaven.removeComponent(a)
        assert not self.heaven.hasComponent('fake')
        self.assertRaises(KeyError, self.heaven.removeComponent, a)

    def testComponentEatersEmpty(self):
        a = FakeComponentAvatar('fake')
        self.heaven.avatars['fake'] = a
        assert self.heaven._getComponentEatersData(a) == []
        
    def testComponentsEaters(self):
        a = FakeComponentAvatar('foo', ['bar:default', 'baz:default'])
        self.heaven.avatars['foo'] = a
        a2 = FakeComponentAvatar('bar', port=1000, listen_host='bar-host')
        self.heaven.avatars['bar'] = a2
        a3 = FakeComponentAvatar('baz', port=1001, listen_host='baz-host')
        self.heaven.avatars['baz'] = a3

        self.heaven._feederSet.addFeeders(a2)
        self.heaven._feederSet.addFeeders(a3)
        
        eaters = self.heaven._getComponentEatersData(a)
        assert len(eaters) == 2
        assert ('bar:default', 'bar-host', 1000) in eaters
        assert ('baz:default', 'baz-host', 1001) in eaters        

if __name__ == '__main__':
     unittest.main()
