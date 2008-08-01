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

import gobject
from twisted.trial import unittest

from flumotion.common import testsuite
from flumotion.common import errors
from flumotion.component.feedcomponent import ParseLaunchComponent


class PipelineTest(ParseLaunchComponent):

    def __init__(self, eaters=None, feeders=None, pipeline='test-pipeline'):
        self.__pipeline = pipeline
        self._eater = eaters or {}
        self._feed = feeders or []
        config = {'name': 'fake',
                  'avatarId': '/default/fake',
                  'eater': self._eater,
                  'feed': self._feed,
                  'plugs': {},
                  'properties': {},
                  # clock master prevents the comp from being
                  # instantiated
                  'clock-master': '/some/component'}
        ParseLaunchComponent.__init__(self, config)

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


class TestExpandElementNames(testsuite.TestCase):

    def setUp(self):
        self.p = PipelineTest([], [])

    def tearDown(self):
        return self.p.stop()

    def testOddDelimeters(self):
        self.assertRaises(TypeError, self.p.parse_pipeline,
                          '@ this:is:wrong @ ! because ! @')


class TestParser(testsuite.TestCase):

    def parse(self, unparsed, correctresultproc, eaters=None, feeders=None):
        comp = PipelineTest(eaters, feeders, unparsed)
        result = comp.parse_pipeline(unparsed)
        self.assertEquals(result, correctresultproc(comp))
        comp.stop()

    def testSimpleOneElement(self):
        self.parse('foobar', lambda p: 'foobar')

    def testSimpleTwoElements(self):
        self.parse('foo ! bar', lambda p: 'foo ! bar')

    def testOneSource(self):
        self.parse('@eater:default@ ! bar',
                   lambda p: '%s ! bar' % (p.get_eater_template('default')),
                   {'qux': [('foo:bar', 'default')]})

    def testOneSourceWithout(self):
        self.parse('bar',
                   lambda p: '%s ! bar' % (p.get_eater_template('default')),
                   {'qux': [('foo:quoi', 'default')]})

    def testOneFeed(self):
        self.parse('foo ! @feeder:bar@',
                   lambda p: 'foo ! %s' % (p.get_feeder_template('bar')),
                   {}, ['bar'])

    def testOneFeedWithout(self):
        self.parse('foo',
                   lambda p: 'foo ! %s' % (p.get_feeder_template('bar')),
                   {}, ['bar'])

    def testTwoSources(self):
        self.parse('@eater:foo@ ! @eater:bar@ ! baz',
                   lambda p: '%s ! %s ! baz' % (p.get_eater_template('foo'),
                                      p.get_eater_template('bar')),
                   {'qux': [('baz:default', 'foo')],
                    'zag': [('qux:default', 'bar')]})

    def testTwoFeeds(self):
        self.parse('foo ! @feeder:bar@ ! @feeder:baz@',
                   lambda p: 'foo ! %s ! %s' % (p.get_feeder_template('bar'),
                                      p.get_feeder_template('baz')),
                   {}, ['bar', 'baz'])

    def testTwoBoth(self):
        self.parse(
            '@eater:src1@ ! @eater:src2@ ! @feeder:feed1@ ! @feeder:feed2@',
            lambda p: '%s ! %s ! %s ! %s' % (p.get_eater_template('src1'),
                                             p.get_eater_template('src2'),
                                             p.get_feeder_template('feed1'),
                                             p.get_feeder_template('feed2')),
            {'qux': [('comp1:default', 'src1')],
             'zag': [('comp2:default', 'src2')]},
            ['feed1', 'feed2'])

    def testErrors(self):
        comp = PipelineTest(None, None, '')
        d = self.assertFailure(comp.waitForHappy(), errors.ComponentStartError)
        d.addCallback(lambda _: comp.stop())

if __name__ == '__main__':
    unittest.main()
