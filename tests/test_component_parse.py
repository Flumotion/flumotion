import unittest

from flumotion.server.component import ParseLaunchComponent

class PipelineTest(ParseLaunchComponent):
    def __init__(self, sources, feeds):
        self.component_name = '<fake>'
        self.sources = sources
        self.feeds = feeds
        self.remote = None
        
def pipelineFactory(pipeline, sources=[], feeds=[]):
    p = PipelineTest(sources, feeds)
    return p.parse_pipeline(pipeline)

SOURCE = ParseLaunchComponent.SOURCE_TMPL
FEED = ParseLaunchComponent.FEED_TMPL

class TestParser(unittest.TestCase):
    def testSimple(self):
        assert pipelineFactory('foobar') == 'foobar'
        assert pipelineFactory('foo ! bar') == 'foo ! bar'

    def testOneSource(self):
        res = pipelineFactory('@foo ! bar', ['foo'])
        assert res == '%s name=foo ! bar' % SOURCE, res

    def testOneSourceWithout(self):
        res = pipelineFactory('bar', ['foo'])
        assert res == '%s name=foo ! bar' % SOURCE, res

    def testOneFeed(self):
        res = pipelineFactory('foo ! :bar', [], ['bar'])
        assert res == 'foo ! %s name=bar' % FEED, res
        
    def testOneFeedWithout(self):
        res = pipelineFactory('foo', [], ['bar'])
        assert res == 'foo ! %s name=bar' % FEED, res

    def testTwoSources(self):
        res = pipelineFactory('@foo ! @bar ! baz', ['foo', 'bar'])
        assert res == '%s name=foo ! %s name=bar ! baz' \
               % (SOURCE, SOURCE), res

    def testTwoFeeds(self):
        res = pipelineFactory('foo ! :bar ! :baz', [], ['bar', 'baz'])
        assert res == 'foo ! %s name=bar ! %s name=baz' \
               % (FEED, FEED), res

    def testTwoBoth(self):
        res = pipelineFactory('@source1 ! @source2 ! :feed1 ! :feed2',
                              ['source1', 'source2',],
                              ['feed1', 'feed2'])
        assert res == ('%s name=source1 ! %s name=source2 ! ' % \
                       (SOURCE, SOURCE) + 
                       '%s name=feed1 ! %s name=feed2' % \
                       (FEED, FEED))
    def testErrors(self):
        self.assertRaises(TypeError, pipelineFactory, '')

if __name__ == '__main__':
    unittest.main()
