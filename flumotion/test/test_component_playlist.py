# -*- Mode: Python; test-case-name: flumotion.test.test_component_httpstreamer -*-
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

from flumotion.component.producers.playlist import playlistparser

class FakeProducer(object):
    position = -1

    def scheduleItem(self, item):
        return item

    def unscheduleItem(self, item):
        pass

    def adjustItemScheduling(self, item):
        pass

    def getCurrentPosition(self):
        return self.position

class TestPlaylist(unittest.TestCase):
    def setUp(self):
        producer = FakeProducer()

        self.playlist = playlistparser.Playlist(producer)

    def checkItems(self, expectedlen):
        l = 0
        cur = self.playlist.items
        if cur:
            self.assertEquals(cur.prev, None)

        while cur:
            l += 1
            # Check consistency of links
            if cur.next:
                self.assertEquals(cur, cur.next.prev)
            cur = cur.next

        self.assertEquals(l, expectedlen)

    def testAddSingleItem(self):
        self.playlist.addItem(None, 0, "file:///testuri", 0, 100, True, True)

        self.assert_(self.playlist._itemsById.has_key(None))
        self.assertEquals(len(self.playlist._itemsById[None]), 1)

        self.checkItems(1)
        pass

    def testAddRemoveSingleItem(self):
        self.playlist.addItem('id1', 0, "file:///testuri", 0, 100, True, True)
        self.playlist.removeItems('id1')

        self.assert_(not self.playlist._itemsById.has_key('id1'))

        self.checkItems(0)

    def testAddRemoveMultipleItems(self):
        self.playlist.addItem('id1', 0, "file:///testuri", 0, 100, True, True)
        self.playlist.addItem('id1', 100, "file:///testuri2", 0, 100, True, True)
        self.playlist.addItem('id2', 200, "file:///testuri2", 0, 100, True, True)
        self.checkItems(3)

        self.playlist.removeItems('id1')
        self.assert_(not self.playlist._itemsById.has_key('id1'))
        self.assert_(self.playlist._itemsById.has_key('id2'))
        self.checkItems(1)

    def testAddOverlappingItems(self):
        first = self.playlist.addItem('id1', 0, "file:///testuri", 0, 100, 
            True, True)
        self.assertEquals(first.duration, 100)
        second = self.playlist.addItem('id1', 50, "file:///testuri", 0, 100, 
            True, True)

        self.checkItems(2)
        # First one should have had duration adjusted
        self.assertEquals(first.duration, 50)

        third = self.playlist.addItem('id1', 25, "file:///testuri", 0, 150, 
            True, True)
        # Second should have been deleted
        self.assert_(second not in self.playlist._itemsById['id1'])
        self.checkItems(2)
        self.assertEquals(first.duration, 25)

if __name__ == '__main__':
    unittest.main()
