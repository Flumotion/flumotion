# -*- Mode: Python; test-case-name: flumotion.test.test_hls_ring -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2009,2010 Fluendo, S.L. (www.fluendo.com).
# All rights reserved.
# flumotion-fragmented-streaming - Flumotion Advanced fragmented streaming

# Licensees having purchased or holding a valid Flumotion Advanced
# Streaming Server license may use this file in accordance with the
# Flumotion Advanced Streaming Server Commercial License Agreement.
# See "LICENSE.Flumotion" in the source distribution for more information.

# Headers in this file shall remain intact.

from twisted.trial import unittest

from flumotion.component.consumers.hlsstreamer import hlsring


class TestHLSRing(unittest.TestCase):

    MAIN_PLAYLIST = """\
#EXTM3U
#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=300000
http://localhost:8000/stream.m3u8
"""

    STREAM_PLAYLIST = """\
#EXTM3U
#EXT-X-ALLOW-CACHE:YES
#EXT-X-TARGETDURATION:2
#EXT-X-MEDIA-SEQUENCE:1
#EXTINF:2,Title
http://localhost:8000/fragment-1.webm
#EXTINF:2,Title
http://localhost:8000/fragment-2.webm
#EXTINF:2,Title
http://localhost:8000/fragment-3.webm
#EXTINF:2,Title
http://localhost:8000/fragment-4.webm
#EXTINF:2,Title
http://localhost:8000/fragment-5.webm
"""
    STREAM_WITH_GKID_PLAYLIST = """\
#EXTM3U
#EXT-X-ALLOW-CACHE:YES
#EXT-X-TARGETDURATION:2
#EXT-X-MEDIA-SEQUENCE:1
#EXTINF:2,Title
http://localhost:8000/fragment-1.webm?GKID=%s
#EXTINF:2,Title
http://localhost:8000/fragment-2.webm?GKID=%s
#EXTINF:2,Title
http://localhost:8000/fragment-3.webm?GKID=%s
#EXTINF:2,Title
http://localhost:8000/fragment-4.webm?GKID=%s
#EXTINF:2,Title
http://localhost:8000/fragment-5.webm?GKID=%s
"""

    def setUp(self):
        self.ring = hlsring.HLSRing('live.m3u8', 'stream.m3u8',
                '300000', 'title', window=5)
        self.ring.setHostname('localhost')

    def testAddFragment(self):
        self.ring.addFragment('', 0, 10)
        self.assertEqual(len(self.ring._fragmentsDict), 1)
        self.assertEqual(len(self.ring._availableFragments), 1)
        self.assert_(self.ring._availableFragments[0] in
                self.ring._fragmentsDict)

    def testGetFragment(self):
        self.ring.addFragment('string', 0, 10)
        fragment = self.ring.getFragment(self.ring._availableFragments[0])
        self.assertEqual(fragment, 'string')

    def testWindowSize(self):
        for i in range(11):
            self.ring.addFragment('fragment-%s' % i, i, 10)
        self.assertEqual(len(self.ring._availableFragments), 11)
        self.assertEqual(len(self.ring._fragmentsDict), 11)
        self.ring.addFragment('fragment-12', 0, 10)
        self.assertEqual(len(self.ring._availableFragments), 11)
        self.assertEqual(len(self.ring._fragmentsDict), 11)
        self.assert_('fragment-0' not in self.ring._fragmentsDict)
        self.assert_('fragment-0' not in self.ring._availableFragments)

    def testDuplicateSegments(self):
        for i in range(6):
            self.ring.addFragment('fragment', 0, 10)
        self.assertEqual(len(self.ring._availableFragments), 1)
        self.assertEqual(len(self.ring._fragmentsDict), 1)

    def testHostname(self):
        self.ring.setHostname('/localhost:8000')
        self.assertEqual(self.ring._hostname, 'http://localhost:8000/')

    def testMainPlaylist(self):
        self.ring._hostname = 'http://localhost:8000/'
        self.assertEqual(self.ring._renderMainPlaylist(''), self.MAIN_PLAYLIST)

    def testStreamPlaylist(self):
        self.ring._hostname = 'http://localhost:8000/'
        self.ring.title = 'Title'
        for i in range(6):
            self.ring.addFragment('', i, 2)
        self.assertEqual(self.ring._renderStreamPlaylist(''),
                self.STREAM_PLAYLIST)

    def testStreamPlaylistiWithGKID(self):
        ID = '12345'
        args = {}
        args['GKID'] = [ID]
        self.ring._hostname = 'http://localhost:8000/'
        self.ring.title = 'Title'
        for i in range(6):
            self.ring.addFragment('', i, 2)
        self.assertEqual(self.ring._renderStreamPlaylist(args),
                self.STREAM_WITH_GKID_PLAYLIST % tuple(5*[ID]))


if __name__ == '__main__':
    unittest.main()
