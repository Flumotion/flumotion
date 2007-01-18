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

from flumotion.component.feedcomponent import ParseLaunchComponent
from flumotion.twisted.defer import defer_generator_method

import twisted.copyright #T1.3
#T1.3
def weHaveAnOldTwisted():
    return twisted.copyright.version[0] < '2'

class PipelineTest(ParseLaunchComponent):
    def __init__(self, eaters=None, feeders=None, pipeline='test-pipeline'):
        self.__pipeline = pipeline
        self._source = eaters or []
        self._feed = feeders or []

        ParseLaunchComponent.__init__(self)

    def config(self):
        config = {'name': 'fake',
                  'source': self._source,
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

    def set_pipeline(self, pipeline):
        self.pipeline = pipeline
        
def pipelineFactory(pipeline, eaters=None, feeders=None):
    t = PipelineTest(pipeline=pipeline, eaters=eaters, feeders=feeders)
    d = defer.Deferred()
    dd = t.config()
    def pipelineConfigCallback(result):
        res = None
        try:
            res = t.parse_pipeline(pipeline)
            t.stop()
            d.callback(res)
        except Exception, e:
            d.errback(e)
    dd.addCallback(pipelineConfigCallback)
    return d

EATER = ParseLaunchComponent.EATER_TMPL
FEEDER = ParseLaunchComponent.FEEDER_TMPL

class TestExpandElementName(unittest.TestCase):
    def setUp(self):
        self.p = PipelineTest([], [])
        d = self.p.config()
        if weHaveAnOldTwisted():
            unittest.deferredResult(d)
        else:
            yield d
    setUp = defer_generator_method(setUp)

    def tearDown(self):
        self.p.stop()

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
        d = self.p.config()
        if weHaveAnOldTwisted():
            unittest.deferredResult(d)
        else:
            yield d
    setUp = defer_generator_method(setUp)

    def tearDown(self):
        self.p.stop()

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

    def _pipelineFactoryCallback(self, result, correctresult):
        self.assertEquals(result, correctresult)

    def testSimpleOneElement(self):
        d = pipelineFactory('foobar')
        if weHaveAnOldTwisted():
            result = unittest.deferredResult(d)
            self.assertEquals(result, 'foobar')
        else:
            d.addCallback(self._pipelineFactoryCallback, 'foobar')
            return d

    def testSimpleTwoElements(self):
        d = pipelineFactory('foo ! bar')
        if weHaveAnOldTwisted():
            result = unittest.deferredResult(d)
            self.assertEquals(result, 'foo ! bar')
        else:
            d.addCallback(self._pipelineFactoryCallback, 'foo ! bar')
            return d

    def testOneSource(self):
        d  = pipelineFactory('@eater:foo@ ! bar', ['foo'])
        if weHaveAnOldTwisted():
            res = unittest.deferredResult(d)
            self.assertEquals(res, '%s ! bar' % self._eater('foo:default'))
        else:
            d.addCallback(self._pipelineFactoryCallback, '%s ! bar' % (
                self._eater('foo:default')))
            return d

    def testOneSourceWithout(self):
        d = pipelineFactory('bar', ['foo'])
        if weHaveAnOldTwisted():
            res = unittest.deferredResult(d)
            self.assertEquals(res, '%s ! bar' % self._eater('foo:default'))
        else:
            d.addCallback(self._pipelineFactoryCallback, '%s ! bar' % (
                self._eater('foo:default')))
            return d

    def testOneFeed(self):
        d = pipelineFactory('foo ! @feeder::bar@', [], ['bar'])
        if weHaveAnOldTwisted():
            res = unittest.deferredResult(d)
            self.assertEquals(res, 'foo ! %s' % self._feeder('fake:bar'))
        else:
            d.addCallback(self._pipelineFactoryCallback, 'foo ! %s' % (
                self._feeder('fake:bar')))
            return d
        
    def testOneFeedWithout(self):
        d = pipelineFactory('foo', [], ['bar'])
        if weHaveAnOldTwisted():
            res = unittest.deferredResult(d)
            self.assertEquals(res, 'foo ! %s' % self._feeder('fake:bar'))
        else:
            d.addCallback(self._pipelineFactoryCallback, 'foo ! %s' % (
                self._feeder('fake:bar')))
            return d

    def testTwoSources(self):
        d = pipelineFactory('@eater:foo@ ! @eater:bar@ ! baz', ['foo', 'bar'])
        if weHaveAnOldTwisted():
            res = unittest.deferredResult(d)
            self.assertEquals(res, '%s ! %s ! baz' % (
               self._eater('foo:default'), self._eater('bar:default')))
        else:
            d.addCallback(self._pipelineFactoryCallback, '%s ! %s ! baz' % (
               self._eater('foo:default'), self._eater('bar:default')))
            return d

    def testTwoFeeds(self):
        d = pipelineFactory('foo ! @feeder::bar@ ! @feeder::baz@', [],
            ['bar', 'baz'])
        if weHaveAnOldTwisted():
            res = unittest.deferredResult(d)
            self.assertEquals(res, 'foo ! %s ! %s' % (
                self._feeder('fake:bar'), self._feeder('fake:baz')))
        else:
            d.addCallback(self._pipelineFactoryCallback, 'foo ! %s ! %s' % (
               self._feeder('fake:bar'), self._feeder('fake:baz')))
            return d

    def testTwoBoth(self):
        d = pipelineFactory(
            '@eater:comp1@ ! @eater:comp2@ ! @feeder::feed1@ ! @feeder::feed2@',
                              ['comp1', 'comp2',],
                              ['feed1', 'feed2'])
        if weHaveAnOldTwisted():
            res = unittest.deferredResult(d)
            self.assertEquals(res, '%s ! %s ! %s ! %s' % (
                self._eater('comp1:default'), self._eater('comp2:default'),
                self._feeder('fake:feed1'), self._feeder('fake:feed2')))
        else:
            d.addCallback(self._pipelineFactoryCallback, '%s ! %s ! %s ! %s' % (
                self._eater('comp1:default'), self._eater('comp2:default'),
                self._feeder('fake:feed1'), self._feeder('fake:feed2')))
            return d

    def testErrors(self):
        d = pipelineFactory('')
        if weHaveAnOldTwisted():
            failure = unittest.deferredError(d)
            assert(isinstance(failure, failure.Failure))
            #self.assertRaises(failure.Failure, unittest.deferredResult(d), '')
        else:
            def pipelineFactoryErrback(failure):
                assert(isinstance(failure, failure.Failure))
            d.addCallback(pipelineFactoryErrback)
            return d
    testErrors.skip = "Help, I cant seem to port properly"
    
if __name__ == '__main__':
    unittest.main()
