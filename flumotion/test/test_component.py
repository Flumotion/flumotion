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
    def __init__(self, eater_config, feeder_config):
        self.__gobject_init__()
        self.name = 'fake'
        self.remote = None

        self.parseEaterConfig(eater_config)
        self.parseFeederConfig(feeder_config)
        
def pipelineFactory(pipeline, eater_config=[], feeder_config=[]):
    p = PipelineTest(eater_config, feeder_config)
    return p.parse_pipeline(pipeline)

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
    def testSimple(self):
        assert pipelineFactory('foobar') == 'foobar'
        assert pipelineFactory('foo ! bar') == 'foo ! bar'

    def testOneSource(self):
        res = pipelineFactory('@eater:foo@ ! bar', ['foo'])
        assert res == ('%s name=eater:foo:default ' % \
                       EATER +
                       '! tee name=tee-eater:foo:default ! bar'), res

    def testOneSourceWithout(self):
        res = pipelineFactory('bar', ['foo'])
        assert res == ('%s name=eater:foo:default ' % \
                       EATER +
                       '! tee name=tee-eater:foo:default ! bar'), res

    def testOneFeed(self):
        res = pipelineFactory('foo ! @feeder::bar@', [], ['bar'])
        assert res == ('foo ! tee name=tee-feeder:fake:bar ' +
                       '! %s name=feeder:fake:bar' % FEEDER), res
        
    def testOneFeedWithout(self):
        res = pipelineFactory('foo', [], ['bar'])
        assert res == ('foo ! tee name=tee-feeder:fake:bar ' +
                       '! %s name=feeder:fake:bar' % FEEDER), res

    def testTwoSources(self):
        res = pipelineFactory('@eater:foo@ ! @eater:bar@ ! baz', ['foo', 'bar'])
        assert res == ('%s name=eater:foo:default ' % \
                       EATER + 
                       '! tee name=tee-eater:foo:default ' +
                       '! %s name=eater:bar:default ' % \
                       EATER +
                       '! tee name=tee-eater:bar:default ! baz'), res

    def testTwoFeeds(self):
        res = pipelineFactory('foo ! @feeder::bar@ ! @feeder::baz@', [], ['bar', 'baz'])
        assert res == ('foo ! tee name=tee-feeder:fake:bar ' +
                       '! %s name=feeder:fake:bar ' % FEEDER +
                       '! tee name=tee-feeder:fake:baz ' +
                       '! %s name=feeder:fake:baz' % FEEDER), res

    def testTwoBoth(self):
        res = pipelineFactory('@eater:comp1@ ! @eater:comp2@ ! @feeder::feed1@ ! @feeder::feed2@',
                              ['comp1', 'comp2',],
                              ['feed1', 'feed2'])
        assert res == ('%s name=eater:comp1:default ' % EATER +
                       '! tee name=tee-eater:comp1:default ' +
                       '! %s name=eater:comp2:default ' % EATER +
                       '! tee name=tee-eater:comp2:default ' +
                       '! tee name=tee-feeder:fake:feed1 ' + 
                       '! %s name=feeder:fake:feed1 ' % FEEDER +
                       '! tee name=tee-feeder:fake:feed2 ' +
                       '! %s name=feeder:fake:feed2' % FEEDER)

    def testErrors(self):
        self.assertRaises(TypeError, pipelineFactory, '')
    testErrors.skip = "Empty pipeline should raise TypeError"
    
if __name__ == '__main__':
    unittest.main()
