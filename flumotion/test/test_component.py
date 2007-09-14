# -*- Mode: Python; test-case-name: flumotion.test.test_component -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007 Fluendo, S.L. (www.fluendo.com).
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

from twisted.trial import unittest

import common

from twisted.python import failure
from twisted.internet import defer

from flumotion.common import errors
from flumotion.component.feedcomponent import ParseLaunchComponent
from flumotion.twisted.defer import defer_generator_method

class PipelineTest(ParseLaunchComponent):
    def __init__(self, eaters=None, feeders=None, pipeline='test-pipeline'):
        self.__pipeline = pipeline
        self._eater = eaters or {}
        self._feed = feeders or []
        ParseLaunchComponent.__init__(self)

    def config(self):
        config = {'name': 'fake',
                  'eater': self._eater,
                  'feed': self._feed,
                  'plugs': {},
                  'properties': {}}

        return self.setup(config)

    def create_pipeline(self):
        unparsed = self.__pipeline
        self.pipeline_string = self.parse_pipeline(unparsed)

        try:
            # don't bother creating a gstreamer pipeline
            # pipeline = gst.parse_launch(self.pipeline_string)
            return None
        except gobject.GError, e:
            self.warning('Could not parse pipeline: %s' % e.message)
            raise errors.PipelineParseError(e.message)

    def connect_feeders(self, pipeline):
        pass
        
    def set_pipeline(self, pipeline):
        self.pipeline = pipeline
        
def pipelineFactory(pipeline, eaters=None, feeders=None):
    t = PipelineTest(pipeline=pipeline, eaters=eaters, feeders=feeders)
    d = defer.Deferred()
    dd = t.config()
    def pipelineConfigCallback(result):
        res = t.parse_pipeline(pipeline)
        t.stop()
        return res
    def _eb(failure):
        t.stop()
        return failure

    dd.addCallbacks(pipelineConfigCallback, _eb)
    # return a tuple because we need a reference to the PipelineTest object
    return (dd, t)

class TestExpandElementNames(unittest.TestCase):
    def setUp(self):
        self.p = PipelineTest([], [])
        d = self.p.config()
        yield d
    setUp = defer_generator_method(setUp)

    def tearDown(self):
        self.p.stop()

    def testOddDelimeters(self):
        self.assertRaises(TypeError, self.p.parse_pipeline,
                          '@ this:is:wrong @ ! because ! @')

class TestParser(unittest.TestCase):
    def _pipelineFactoryCallback(self, result, correctresult):
        self.assertEquals(result, correctresult)

    def testSimpleOneElement(self):
        d, pipeline = pipelineFactory('foobar')
        d.addCallback(self._pipelineFactoryCallback, 'foobar')
        return d

    def testSimpleTwoElements(self):
        d, pipeline = pipelineFactory('foo ! bar')
        d.addCallback(self._pipelineFactoryCallback, 'foo ! bar')
        return d

    def testOneSource(self):
        d, pipeline = pipelineFactory('@eater:default@ ! bar',
                                      {'qux': [('foo:bar', 'default')]})
        d.addCallback(self._pipelineFactoryCallback, '%s ! bar' % (
            pipeline.get_eater_template('default')))
        return d

    def testOneSourceWithout(self):
        d, pipeline = pipelineFactory('bar',
                                      {'qux': [('foo:quoi', 'default')]})
        d.addCallback(self._pipelineFactoryCallback, '%s ! bar' % (
            pipeline.get_eater_template('default')))
        return d

    def testOneFeed(self):
        d, pipeline = pipelineFactory('foo ! @feeder:bar@', {}, ['bar'])
        d.addCallback(self._pipelineFactoryCallback, 'foo ! %s' % (
            pipeline.get_feeder_template('bar')))
        return d
        
    def testOneFeedWithout(self):
        d, pipeline = pipelineFactory('foo', {}, ['bar'])
        d.addCallback(self._pipelineFactoryCallback, 'foo ! %s' % (
            pipeline.get_feeder_template('bar')))
        return d

    def testTwoSources(self):
        d, pipeline = pipelineFactory('@eater:foo@ ! @eater:bar@ ! baz', 
                                      {'qux': [('baz:default', 'foo')],
                                       'zag': [('qux:default', 'bar')]})
        d.addCallback(self._pipelineFactoryCallback, '%s ! %s ! baz' % (
           pipeline.get_eater_template('foo'), 
           pipeline.get_eater_template('bar')))
        return d

    def testTwoFeeds(self):
        d, pipeline = pipelineFactory('foo ! @feeder:bar@ ! @feeder:baz@', {},
            ['bar', 'baz'])
        d.addCallback(self._pipelineFactoryCallback, 'foo ! %s ! %s' % (
           pipeline.get_feeder_template('bar'), 
           pipeline.get_feeder_template('baz')))
        return d

    def testTwoBoth(self):
        d, pipeline = pipelineFactory(
            '@eater:src1@ ! @eater:src2@ ! @feeder:feed1@ ! @feeder:feed2@',
            {'qux': [('comp1:default', 'src1')],
             'zag': [('comp2:default', 'src2')]},
            ['feed1', 'feed2'])
        d.addCallback(self._pipelineFactoryCallback, '%s ! %s ! %s ! %s' % (
            pipeline.get_eater_template('src1'), 
            pipeline.get_eater_template('src2'),
            pipeline.get_feeder_template('feed1'), 
            pipeline.get_feeder_template('feed2')))
        return d

    def testErrors(self):
        d, pipeline = pipelineFactory('')
        def _cb(r):
            self.fail("Didn't get expected failure, received %r" % (r,))
        def _eb(failure):
            failure.trap(errors.ComponentSetupHandledError)
            return failure.value
        d.addCallbacks(_cb, _eb)
        return d
    
if __name__ == '__main__':
    unittest.main()
