# -*- Mode: Python; test-case-name: flumotion.test.test_component -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# flumotion/test/test_component.py: test for flumotion.component.component
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

from twisted.trial import unittest

import common

from flumotion.component.component import ParseLaunchComponent

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
