from common import unittest

from flumotion.server import controller

class FakeComponentPerspective:
    def __init__(self, name='fake', sources=[], port=-1, listen_host='listen-host'):
        self.name = name
        self.sources = sources
        self.port = port
        self.listen_host = listen_host
        
    def getFeeds(self, long):
        if long:
            return [self.name + ':default']
        else:
            return ['default']

    def getListenHost(self):
        return self.listen_host

    def getListenPort(self, *args):
        return self.port
    
    def getTransportPeer(self):
        return 0, '127.0.0.1', 0

    def getName(self):
        return self.name

    def getSources(self):
        return self.sources
    
class TestController(unittest.TestCase):
    def setUp(self):
        self.cont = controller.Controller()

    def testGetPerspective(self):
        p = self.cont.getPerspective('foo-bar-baz')
        assert isinstance(p, controller.ComponentPerspective)

        #self.assertRaises(AssertionError,
        #                  self.cont.getPerspective, 'does-not-exist')

    def testIsLocalComponent(self):
        c = FakeComponentPerspective()
        self.cont.addComponent(c)
        assert self.cont.isLocalComponent(c)
        
    def testIsStarted(self):
        c = self.cont.getPerspective('prod')
        assert not self.cont.isComponentStarted('prod')
        c.started = True # XXX: Use controller.componentStart
        assert self.cont.isComponentStarted('prod')

    def testGetComponent(self):
        c = self.cont.getPerspective('prod')
        assert self.cont.getComponent('prod') == c

    def testHasComponent(self):
        c = self.cont.getPerspective('prod')
        assert self.cont.hasComponent('prod')
        self.cont.removeComponent(c)
        assert not self.cont.hasComponent('prod')
        self.assertRaises(KeyError, self.cont.removeComponent, c)
        
    def testAddComponent(self):
        c = FakeComponentPerspective('fake')
        self.cont.addComponent(c)
        assert self.cont.hasComponent('fake')
        self.assertRaises(KeyError, self.cont.addComponent, c)
        
    def testRemoveComponent(self):
        assert not self.cont.hasComponent('fake')
        c = FakeComponentPerspective('fake')
        self.assertRaises(KeyError, self.cont.removeComponent, c)
        self.cont.addComponent(c)
        assert self.cont.hasComponent('fake')
        self.cont.removeComponent(c)
        assert not self.cont.hasComponent('fake')
        self.assertRaises(KeyError, self.cont.removeComponent, c)

    def testSourceComponentsEmpty(self):
        c = FakeComponentPerspective('fake')
        self.cont.addComponent(c)
        assert self.cont.getSourceComponents(c) == []
        
    def testSourceComponents(self):
        c = FakeComponentPerspective('foo', ['bar', 'baz'])
        self.cont.addComponent(c)
        c2 = FakeComponentPerspective('bar', port=1000, listen_host='bar-host')
        self.cont.addComponent(c2)
        c3 = FakeComponentPerspective('baz', port=1001, listen_host='baz-host')
        self.cont.addComponent(c3)
        self.cont.feed_manager.addFeeds(c2)
        self.cont.feed_manager.addFeeds(c3)
        
        sources = self.cont.getSourceComponents(c)
        assert len(sources) == 2
        assert ('bar', 'bar-host', 1000) in sources
        assert ('baz', 'baz-host', 1001) in sources        

if __name__ == '__main__':
     unittest.main()
