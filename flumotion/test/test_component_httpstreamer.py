# -*- test-case-name: flumotion.test.test_component_httpstreamer -*-
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

from flumotion.common import testsuite
from flumotion.component.consumers.httpstreamer import httpstreamer

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


class TestOldProperties(StreamerTestCase):
    "Test that old properties with underscores in the name get converted."
    properties = {
        u'user_limit': 1024,
        u'mount_point': '/',
        u'bandwidth_limit': 10,
        u'port': 8800,
        u'burst_on_connect': True,
    }

    def testPropertiesConverted(self):
        # test that the old-style properties were renamed to new-style
        props = self.component.config['properties']
        for key in ('user_limit', 'mount_point', 'bandwidth_limit',
            'burst_on_connect'):
            self.failIf(key in props)
        self.assertEquals(props['client-limit'], 1024)
        self.assertEquals(props['bandwidth-limit'], 10)
        self.assertEquals(props['mount-point'], '/')
        self.assertEquals(props['burst-on-connect'], True)


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
