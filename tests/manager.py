from common import unittest

from flumotion.server import manager

class FakeComponentPerspective:
    def __init__(self, name='fake', eaters=[], port=-1, listen_host='listen-host'):
        self.name = name
        self.eaters = eaters
        self.port = port
        self.listen_host = listen_host
        
    def getFeeders(self, long):
        if long:
            return [self.name + ':default']
        else:
            return ['default']

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

class TestManager(unittest.TestCase):
    def setUp(self):
        self.manager = manager.Manager()

    def testGetPerspective(self):
        p = self.manager.getAvatar('foo-bar-baz')
        assert isinstance(p, manager.ComponentAvatar)

        #self.assertRaises(AssertionError,
        #                  self.manager.getPerspective, 'does-not-exist')

    def testIsLocalComponent(self):
        c = FakeComponentPerspective()
        self.manager.addComponent(c)
        assert self.manager.isLocalComponent(c)
        
    def testIsStarted(self):
        c = self.manager.getAvatar('prod')
        assert not self.manager.isComponentStarted('prod')
        c.started = True # XXX: Use manager.componentStart
        assert self.manager.isComponentStarted('prod')

    def testGetComponent(self):
        c = self.manager.getAvatar('prod')
        assert self.manager.getComponent('prod') == c

    def testHasComponent(self):
        c = self.manager.getAvatar('prod')
        assert self.manager.hasComponent('prod')
        self.manager.removeComponent(c)
        assert not self.manager.hasComponent('prod')
        self.assertRaises(KeyError, self.manager.removeComponent, c)
        
    def testAddComponent(self):
        c = FakeComponentPerspective('fake')
        self.manager.addComponent(c)
        assert self.manager.hasComponent('fake')
        self.assertRaises(KeyError, self.manager.addComponent, c)
        
    def testRemoveComponent(self):
        assert not self.manager.hasComponent('fake')
        c = FakeComponentPerspective('fake')
        self.assertRaises(KeyError, self.manager.removeComponent, c)
        self.manager.addComponent(c)
        assert self.manager.hasComponent('fake')
        self.manager.removeComponent(c)
        assert not self.manager.hasComponent('fake')
        self.assertRaises(KeyError, self.manager.removeComponent, c)

    def testComponentEatersEmpty(self):
        c = FakeComponentPerspective('fake')
        self.manager.addComponent(c)
        assert self.manager.getComponentEaters(c) == []
        
    def testComponentsEaters(self):
        c = FakeComponentPerspective('foo', ['bar', 'baz'])
        self.manager.addComponent(c)
        c2 = FakeComponentPerspective('bar', port=1000, listen_host='bar-host')
        self.manager.addComponent(c2)
        c3 = FakeComponentPerspective('baz', port=1001, listen_host='baz-host')
        self.manager.addComponent(c3)
        self.manager.feeder_set.addFeeders(c2)
        self.manager.feeder_set.addFeeders(c3)
        
        eaters = self.manager.getComponentEaters(c)
        assert len(eaters) == 2
        assert ('bar', 'bar-host', 1000) in eaters
        assert ('baz', 'baz-host', 1001) in eaters        

if __name__ == '__main__':
     unittest.main()
