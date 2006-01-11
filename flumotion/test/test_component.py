# -*- Mode: Python; test-case-name: flumotion.test.test_component -*-
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

import common

from twisted.trial import unittest

from flumotion.component.feedcomponent import ParseLaunchComponent

class PipelineTest(ParseLaunchComponent):
    def __init__(self, eaters=None, feeders=None, pipeline='test-pipeline'):
        config = {'name': 'fake',
                  'source': eaters or [],
                  'feed': feeders or [],
                  'properties': {}}

        self.__pipeline = pipeline

        ParseLaunchComponent.__init__(self)

        # we can short-circuit to setup since we're a test
        self.setup(config)

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

    def set_pipeline(self, pipeline):
        self.pipeline = pipeline
        
def pipelineFactory(pipeline, eaters=None, feeders=None):
    t = PipelineTest(pipeline=pipeline, eaters=eaters, feeders=feeders)
    return t.parse_pipeline(pipeline)

EATER = ParseLaunchComponent.EATER_TMPL
FEEDER = ParseLaunchComponent.FEEDER_TMPL

class TestExpandElementName(unittest.TestCase):
    def setUp(self):
        self.p = PipelineTest([], [])

    def testSpaces(self):
        try:
            r = self.p._expandElementName('test with spaces')
            raise
        except TypeError:
            pass

    def testNoColons(self):
        try:
            r = self.p._expandElementName('testwithoutcolons')
            raise
        except TypeError:
            pass

    def testTooManyColons(self):
        try:
            r = self.p._expandElementName('too:many:colons:here')
            raise
        except TypeError:
            pass

    def testNoEaterFeeder(self):
        try:
            r = self.p._expandElementName(':test')
            raise
        except TypeError:
            pass

    def testEaterComponent(self):
        try:
            r = self.p._expandElementName('eater::feed')
            raise
        except TypeError:
            pass

    def testFeederComponent(self):
        r = self.p._expandElementName('feeder::feed')
        assert r == 'feeder:fake:feed'

    def testFeederDefault(self):
        r = self.p._expandElementName('feeder:test')
        assert r == 'feeder:test:default'
        r = self.p._expandElementName('feeder:test:')
        assert r == 'feeder:test:default'

    def testEaterDefault(self):
        r = self.p._expandElementName('eater:test')
        assert r == 'eater:test:default'
        r = self.p._expandElementName('eater:test:')
        assert r == 'eater:test:default'

    def testFeederEmpty(self):
        r = self.p._expandElementName('feeder::')
        assert r == 'feeder:fake:default'
        r = self.p._expandElementName('feeder:')
        assert r == 'feeder:fake:default'
        try:
            r = self.p._expandElementName('feeder')
            raise
        except TypeError:
            pass

class TestExpandElementNames(unittest.TestCase):
    def setUp(self):
        self.p = PipelineTest([], [])

    def testOddDelimeters(self):
        try:
            r = self.p._expandElementNames('@ this:is:wrong @ ! because ! @')
            raise
        except TypeError:
            pass

    def testPipeline(self):
        r = self.p._expandElementNames('@eater:card @ !  @ feeder::sound @')
        assert r == '@eater:card:default@ !  @feeder:fake:sound@' 
        
class TestParser(unittest.TestCase):
    def _eater(self, name):
        return EATER % { 'name': 'eater:%s' % name }
    def _feeder(self, name):
        return FEEDER % { 'name': 'feeder:%s' % name }

    def testSimple(self):
        self.assertEquals(pipelineFactory('foobar'), 'foobar')
        self.assertEquals(pipelineFactory('foo ! bar'), 'foo ! bar')

    def testOneSource(self):
        res = pipelineFactory('@eater:foo@ ! bar', ['foo'])
        self.assertEquals(res, '%s ! bar' % self._eater('foo:default'))

    def testOneSourceWithout(self):
        res = pipelineFactory('bar', ['foo'])
        self.assertEquals(res, '%s ! bar' % self._eater('foo:default'))

    def testOneFeed(self):
        res = pipelineFactory('foo ! @feeder::bar@', [], ['bar'])
        self.assertEquals(res, 'foo ! %s' % self._feeder('fake:bar'))
        
    def testOneFeedWithout(self):
        res = pipelineFactory('foo', [], ['bar'])
        self.assertEquals(res, 'foo ! %s' % self._feeder('fake:bar'))

    def testTwoSources(self):
        res = pipelineFactory('@eater:foo@ ! @eater:bar@ ! baz', ['foo', 'bar'])
        self.assertEquals(res, '%s ! %s ! baz' % (
               self._eater('foo:default'), self._eater('bar:default')))

    def testTwoFeeds(self):
        res = pipelineFactory('foo ! @feeder::bar@ ! @feeder::baz@', [],
            ['bar', 'baz'])
        self.assertEquals(res, 'foo ! %s ! %s' % (
               self._feeder('fake:bar'), self._feeder('fake:baz')))

    def testTwoBoth(self):
        res = pipelineFactory(
            '@eater:comp1@ ! @eater:comp2@ ! @feeder::feed1@ ! @feeder::feed2@',
                              ['comp1', 'comp2',],
                              ['feed1', 'feed2'])
        self.assertEquals(res, '%s ! %s ! %s ! %s' % (
                self._eater('comp1:default'), self._eater('comp2:default'),
                self._feeder('fake:feed1'), self._feeder('fake:feed2')))

    def testErrors(self):
        self.assertRaises(TypeError, pipelineFactory, '')
    
if __name__ == '__main__':
    unittest.main()
