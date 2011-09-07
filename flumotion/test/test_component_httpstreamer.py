# -*- test-case-name: flumotion.test.test_component_httpstreamer -*-
# vi:si:et:sw=4:sts=4:ts=4

# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008,2009 Fluendo, S.L.
# Copyright (C) 2010,2011 Flumotion Services, S.A.
# All rights reserved.
#
# This file may be distributed and/or modified under the terms of
# the GNU Lesser General Public License version 2.1 as published by
# the Free Software Foundation.
# This file is distributed without any warranty; without even the implied
# warranty of merchantability or fitness for a particular purpose.
# See "LICENSE.LGPL" in the source distribution for more information.
#
# Headers in this file shall remain intact.

from twisted.trial import unittest

from flumotion.common import testsuite
from flumotion.component.consumers.httpstreamer import httpstreamer

attr = testsuite.attr

CONFIG = {
    'feed': [],
    'name': 'http-video',
    'parent': 'default',
    'eater': {'default': [('muxer-video:default', 'default')]},
    'source': ['muxer-video:default'],
    'avatarId': '/default/http-video',
    'clock-master': None,
    'plugs': {
        'flumotion.component.plugs.streamdata.StreamDataProviderPlug': [],
        'flumotion.component.plugs.request.RequestLoggerPlug': [],
    },
    'type': 'http-streamer',
}


class StreamerTestCase(testsuite.TestCase):

    slow = True

    properties = {}
    config = CONFIG

    def setUp(self):
        config = self.getConfig()
        config['properties'] = self.properties.copy()
        self.component = httpstreamer.MultifdSinkStreamer(config)

    def tearDown(self):
        return self.component.stop()

    def getConfig(self):
        # test classes can override this to change/extend config
        return self.config.copy()


class TestStreamDataNoPlug(StreamerTestCase):

    def testGetStreamData(self):
        streamData = self.component.getStreamData()
        # there's no plug, so we get defaults
        self.assertEquals(streamData['protocol'], 'HTTP')
        self.assertEquals(streamData['description'], 'Flumotion Stream')
        self.failUnless(streamData['url'].startswith('http://'))


class TestStreamDataPlug(StreamerTestCase):

    def getConfig(self):
        config = CONFIG.copy()
        sType = 'flumotion.component.plugs.streamdata.StreamDataProviderPlug'
        pType = 'streamdataprovider-example'
        config['plugs'] = {sType: [
            {
                'entries': {
                    'default': {
                        'module-name': 'flumotion.component.plugs.streamdata',
                        'function-name': 'StreamDataProviderExamplePlug',
                    }
                }
            },
        ]}
        return config

    def testGetStreamData(self):
        streamData = self.component.getStreamData()
        self.assertEquals(streamData['protocol'], 'HTTP')
        self.assertEquals(streamData['description'], 'Flumotion Stream')
        self.failUnless(streamData['url'].startswith('http://'))
    # plug is started before component can do getUrl
    testGetStreamData.skip = 'See #1137'


if __name__ == '__main__':
    unittest.main()
