import common
import unittest

from flumotion.manager.component import ParseLaunchComponent

class PipelineTest(ParseLaunchComponent):
    def __init__(self, eaters, feeders):
        self.__gobject_init__()
        self.component_name = '<fake>'
        self.eaters = eaters
        self.feeders = feeders
        self.remote = None
        
def pipelineFactory(pipeline, eaters=[], feeders=[]):
    p = PipelineTest(eaters, feeders)
    return p.parse_pipeline(pipeline)

EATER = ParseLaunchComponent.EATER_TMPL
FEEDER = ParseLaunchComponent.FEEDER_TMPL

class TestParser(unittest.TestCase):
    def testSimple(self):
        assert pipelineFactory('foobar') == 'foobar'
        assert pipelineFactory('foo ! bar') == 'foo ! bar'

    def testOneSource(self):
        res = pipelineFactory('@foo ! bar', ['foo'])
        assert res == '%s name=foo ! bar' % EATER, res

    def testOneSourceWithout(self):
        res = pipelineFactory('bar', ['foo'])
        assert res == '%s name=foo ! bar' % EATER, res

    def testOneFeed(self):
        res = pipelineFactory('foo ! :bar', [], ['bar'])
        assert res == 'foo ! %s name=bar' % FEEDER, res
        
    def testOneFeedWithout(self):
        res = pipelineFactory('foo', [], ['bar'])
        assert res == 'foo ! %s name=bar' % FEEDER, res

    def testTwoSources(self):
        res = pipelineFactory('@foo ! @bar ! baz', ['foo', 'bar'])
        assert res == '%s name=foo ! %s name=bar ! baz' \
               % (EATER, EATER), res

    def testTwoFeeds(self):
        res = pipelineFactory('foo ! :bar ! :baz', [], ['bar', 'baz'])
        assert res == 'foo ! %s name=bar ! %s name=baz' \
               % (FEEDER, FEEDER), res

    def testTwoBoth(self):
        res = pipelineFactory('@eater1 ! @eater2 ! :feeder1 ! :feeder2',
                              ['eater1', 'eater2',],
                              ['feeder1', 'feeder2'])
        assert res == ('%s name=eater1 ! %s name=eater2 ! ' % \
                       (EATER, EATER) + 
                       '%s name=feeder1 ! %s name=feeder2' % \
                       (FEEDER, FEEDER))
    def testErrors(self):
        self.assertRaises(TypeError, pipelineFactory, '')

if __name__ == '__main__':
    unittest.main()
