# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a video streaming server
# Copyright (C) 2004 Fluendo
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Street #330, Boston, MA 02111-1307, USA.

import common
import unittest

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
