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

import time
import tempfile
import gst

from twisted.trial import unittest

from flumotion.component.producers.playlist import playlistparser
from flumotion.common import fxml
from flumotion.common import testsuite


class FakeProducer(object):
    position = -1
    pipeline = gst.Pipeline()

    def scheduleItem(self, item):
        return item

    def unscheduleItem(self, item):
        pass

    def adjustItemScheduling(self, item):
        pass

    def getCurrentPosition(self):
        return self.position


class FakeDiscoverer(object):
    filename = None

    def __init__(self, filename):
        FakeDiscoverer.filename = filename

    def noop(self, *a, **kw):
        pass

    connect = noop
    discover = noop


class TestPlaylist(testsuite.TestCase):

    def setUp(self):
        producer = FakeProducer()

        self.playlist = playlistparser.Playlist(producer)

    def checkItems(self, expectedlen):
        l = 0
        cur = self.playlist.items
        all = []

        if cur:
            self.assertEquals(cur.prev, None)

        while cur:
            all.append(cur)
            self.failUnless(cur in self.playlist._itemsById[cur.id])
            l += 1
            # Check consistency of links
            if cur.next:
                self.assertEquals(cur, cur.next.prev)
            cur = cur.next

        self.assertEquals(l, expectedlen)

        itemsbyidtotal = 0

        for id in self.playlist._itemsById:
            for item in self.playlist._itemsById[id]:
                self.failUnless(item in all)
                itemsbyidtotal += 1
        self.assertEquals(itemsbyidtotal, expectedlen)

    def testAddSingleItem(self):
        self.playlist.addItem(None, 0, "file:///testuri", 0, 100, True, True)

        self.assert_(None in self.playlist._itemsById)
        self.assertEquals(len(self.playlist._itemsById[None]), 1)

        self.checkItems(1)
        pass

    def testAddRemoveSingleItem(self):
        self.playlist.addItem('id1', 0, "file:///testuri", 0, 100, True, True)
        self.playlist.removeItems('id1')

        self.assert_(not 'id1' in self.playlist._itemsById)

        self.checkItems(0)

    def testAddRemoveMultipleItems(self):
        self.playlist.addItem('id1', 0, "file:///testuri",
                              0, 100, True, True)
        self.playlist.addItem('id1', 100, "file:///testuri2",
                              0, 100, True, True)
        self.playlist.addItem('id2', 200, "file:///testuri2",
                              0, 100, True, True)
        self.checkItems(3)

        self.playlist.removeItems('id1')
        self.assert_(not 'id1' in self.playlist._itemsById)
        self.assert_('id2' in self.playlist._itemsById)
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

    def testAddOverlappingItemsReverse(self):
        first = self.playlist.addItem('id1', 50, "file:///testuri", 0, 100,
            True, True)
        self.assertEquals(first.duration, 100)
        second = self.playlist.addItem('id1', 0, "file:///testuri", 0, 100,
            True, True)

        self.checkItems(2)
        # First one should have had duration and timestamp adjusted
        self.assertEquals(first.timestamp, 100)
        self.assertEquals(first.duration, 50)

        third = self.playlist.addItem('id1', 25, "file:///testuri", 0, 150,
            True, True)
        # First should have been deleted now.
        self.assert_(first not in self.playlist._itemsById['id1'])
        self.checkItems(2)
        self.assertEquals(second.duration, 25)

    def testAddRemoveRepeatedly(self):
        self.playlist.addItem('id1', 0, "file:///testuri",
                              0, 100, True, True)
        self.checkItems(1)
        self.playlist.addItem('id2', 100, "file:///testuri",
                              0, 100, True, True)
        self.checkItems(2)

        self.playlist.removeItems('id1')
        self.checkItems(1)
        self.playlist.addItem('id1', 0, "file:///testuri",
                              0, 100, True, True)
        self.checkItems(2)


class TestPlaylistXMLParser(testsuite.TestCase):

    def setUp(self):
        # plant a fake Discoverer class - we're _not_ testing its
        # functionality here
        from gst.extend import discoverer
        self.old_discoverer = discoverer.Discoverer
        discoverer.Discoverer = FakeDiscoverer

        producer = FakeProducer()

        self.playlist = playlistparser.Playlist(producer)
        self.xmlparser = playlistparser.PlaylistXMLParser(self.playlist)

        now = time.time()
        self.pl1 = tempfile.NamedTemporaryFile()
        self.pl1.write('<?xml version="1.0" encoding="UTF-8" ?>\n'
                       '<playlist>\n')
        self.pl1.write('  <entry filename="temp5.ogg" time="%s" offset="0"'
                       ' duration="120"/>\n' %
                       time.strftime('%Y-%m-%dT%H:%M:%S.00Z',
                                     time.gmtime(now + 3600 + 240)))
        self.pl1.write('  <entry filename="temp3.ogg" time="%s" offset="0"'
                       ' duration="120"/>\n' %
                       time.strftime('%Y-%m-%dT%H:%M:%S.00Z',
                                     time.gmtime(now + 3600 + 0)))
        self.pl1.write('  <entry filename="temp4.ogg" time="%s" offset="0"'
                       ' duration="120"/>\n' %
                       time.strftime('%Y-%m-%dT%H:%M:%S.00Z',
                                     time.gmtime(now + 3600 + 120)))
        self.pl1.write('</playlist>\n')
        self.pl1.flush()
        self.pl1.seek(0)

        self.pl2 = tempfile.NamedTemporaryFile()
        self.pl2.write('<?xml version="1.0" encoding="UTF-8" ?>\n'
                       '<playlist>\n')
        self.pl2.write('  <entry filename="temp2.ogg" time="%s" offset="0"'
                       ' duration="120"/>\n' %
                       time.strftime('%Y-%m-%dT%H:%M:%S.00Z',
                                     time.gmtime(now + 1800 + 120)))
        self.pl2.write('  <entry filename="temp0.ogg" time="%s" offset="0"'
                       ' duration="120"/>\n' %
                       time.strftime('%Y-%m-%dT%H:%M:%S.00Z',
                                     time.gmtime(now - 1800))) # in the past!
        self.pl2.write('  <entry filename="temp1.ogg" time="%s" offset="0"'
                       ' duration="120"/>\n' %
                       time.strftime('%Y-%m-%dT%H:%M:%S.00Z',
                                     time.gmtime(now + 1800 + 0)))
        self.pl2.write('</playlist>\n')
        self.pl2.flush()
        self.pl2.seek(0)

        self.pl3 = tempfile.NamedTemporaryFile()
        self.pl3.write('<?xml version="1.0" encoding="UTF-8" ?>\n'
                       '<playlist>\n')
        self.pl3.write('  <entry filename="temp6.ogg" time="%s" offset="0"'
                       ' duration="120"/>\n' %
                       time.strftime('%Y-%m-%dT%H:%M:%S.00Z',
                                     time.gmtime(now + 4800 + 120)))
        self.pl3.write('  <entry filename="tempX.ogg" time="%s" offset="0"'
                       ' duration="120"/>\n' %
                       time.strftime('%Y-%m-%dT%H:%M', # wrong time format!
                                     time.gmtime(now + 4800 + 0)))
        self.pl3.write('</playlist>\n')
        self.pl3.flush()
        self.pl3.seek(0)

    def tearDown(self):
        from gst.extend import discoverer
        discoverer.Discoverer = self.old_discoverer

        self.pl1.close()
        self.pl2.close()
        self.pl3.close()

    def testItemsSortedSingle(self):
        self.xmlparser.parseFile(self.pl1.name)

        self.assertEquals(len(self.xmlparser._pending_items), 2)
        self.assertEquals(self.xmlparser._pending_items[0][0], 'temp4.ogg')
        self.assertEquals(self.xmlparser._pending_items[1][0], 'temp5.ogg')
        self.assertEquals(FakeDiscoverer.filename, 'temp3.ogg')

    def testItemsSortedMultiple(self):
        self.xmlparser.blockDiscovery()
        self.xmlparser.parseFile(self.pl1.name)
        self.xmlparser.parseFile(self.pl2.name)
        self.xmlparser.unblockDiscovery()

        self.assertEquals(len(self.xmlparser._pending_items), 4)
        self.assertEquals([it[0] for it in self.xmlparser._pending_items],
                          ['temp2.ogg', 'temp3.ogg', 'temp4.ogg', 'temp5.ogg'])
        self.assertEquals(FakeDiscoverer.filename, 'temp1.ogg')

    def testParseErrorInBlocking(self):
        self.xmlparser.blockDiscovery()
        self.xmlparser.parseFile(self.pl2.name)
        self.failUnlessRaises(
            fxml.ParserError,
            self.xmlparser.parseFile,
            self.pl3.name)
        self.xmlparser.unblockDiscovery()

        # no matter what happens block level should be 0 after a pair
        # block + unblock calls
        self.assertEquals(self.xmlparser._discovering_blocked, 0)

        self.assertEquals(len(self.xmlparser._pending_items), 2)
        self.assertEquals([it[0] for it in self.xmlparser._pending_items],
                          ['temp2.ogg', 'temp6.ogg'])
        self.assertEquals(FakeDiscoverer.filename, 'temp1.ogg')

if __name__ == '__main__':
    unittest.main()
