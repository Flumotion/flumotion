# -*- Mode: Python -*-
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

import gst
from gst.extend import discoverer

import time
import calendar
from StringIO import StringIO

from xml.dom import Node

from twisted.internet import reactor

from flumotion.common import log, fxml

__version__ = "$Rev$"


class PlaylistItem(object, log.Loggable):

    def __init__(self, piid, timestamp, uri, offset, duration):
        self.id = piid
        self.timestamp = timestamp
        self.uri = uri
        self.offset = offset
        self.duration = duration

        self.hasAudio = True
        self.hasVideo = True

        self.next = None
        self.prev = None


class Playlist(object, log.Loggable):
    logCategory = 'playlist-list'

    def __init__(self, producer):
        """
        Create an initially empty playlist
        """
        self.items = None # PlaylistItem linked list
        self._itemsById = {}

        self.producer = producer

    def _findItem(self, timePosition):
        # timePosition is the position in terms of the clock time
        # Get the item that corresponds to timePosition, or None
        cur = self.items
        while cur:
            if cur.timestamp < timePosition and \
                    cur.timestamp + cur.duration > timePosition:
                return cur
            if cur.timestamp > timePosition:
                return None # fail without having to iterate over everything
            cur = cur.next
        return None

    def _getCurrentItem(self):
        position = self.producer.pipeline.get_clock().get_time()
        item = self._findItem(position)
        self.debug("Item %r found as current for playback position %d",
            item, position)
        return item

    def removeItems(self, piid):
        current = self._getCurrentItem()

        if piid not in self._itemsById:
            return

        items = self._itemsById[piid]
        for item in items:
            self.debug("removeItems: item %r ts: %d", item, item.timestamp)
            if current:
                self.debug("current ts: %d current dur: %d",
                    current.timestamp, current.duration)
            if (current and item.timestamp < current.timestamp +
                    current.duration):
                self.debug("Not removing current item!")
                continue
            self.unlinkItem(item)
            self.producer.unscheduleItem(item)

        del self._itemsById[piid]

    def addItem(self, piid, timestamp, uri, offset, duration,
                hasAudio, hasVideo):
        """
        Add an item to the playlist.

        This may remove overlapping entries, or adjust timestamps/durations of
        entries to make the new one fit.
        """
        current = self._getCurrentItem()
        if current and timestamp < current.timestamp + current.duration:
            self.warning("New object at uri %s starts during current object, "
                "cannot add")
            return None
        # We don't care about anything older than now; drop references to them
        if current:
            self.items = current

        newitem = PlaylistItem(piid, timestamp, uri, offset, duration)
        newitem.hasAudio = hasAudio
        newitem.hasVideo = hasVideo

        if piid in self._itemsById:
            self._itemsById[piid].append(newitem)
        else:
            self._itemsById[piid] = [newitem]

        # prev starts strictly before the new item
        # next starts after the new item, and ends after the
        # end of the new item
        prevItem = nextItem = None
        item = self.items
        while item:
            if item.timestamp < newitem.timestamp:
                prevItem = item
            else:
                break
            item = item.next

        if prevItem:
            item = prevItem.next
        while item:
            if (item.timestamp > newitem.timestamp and
                    item.timestamp + item.duration >
                    newitem.timestamp + newitem.duration):
                nextItem = item
                break
            item = item.next

        if prevItem:
            # Then things between prev and next (next might be None) are to be
            # deleted. Do so.
            cur = prevItem.next
            while cur != nextItem:
                self._itemsById[cur.id].remove(cur)
                if not self._itemsById[cur.id]:
                    del self._itemsById[cur.id]
                self.producer.unscheduleItem(cur)
                cur = cur.next

        # update links.
        if prevItem:
            prevItem.next = newitem
            newitem.prev = prevItem
        else:
            self.items = newitem

        if nextItem:
            newitem.next = nextItem
            nextItem.prev = newitem

        # Duration adjustments -> Reflect into gnonlin timeline
        if prevItem and \
                prevItem.timestamp + prevItem.duration > newitem.timestamp:
            self.debug("Changing duration of previous item from %d to %d",
                prevItem.duration, newitem.timestamp - prevItem.timestamp)
            prevItem.duration = newitem.timestamp - prevItem.timestamp
            self.producer.adjustItemScheduling(prevItem)

        if nextItem and \
            newitem.timestamp + newitem.duration > nextItem.timestamp:
            self.debug("Changing timestamp of next item from %d to %d to fit",
                newitem.timestamp, newitem.timestamp + newitem.duration)
            ts = newitem.timestamp + newitem.duration
            duration = nextItem.duration - (ts - nextItem.timestamp)
            nextItem.duration = duration
            nextItem.timestamp = ts
            self.producer.adjustItemScheduling(nextItem)

        # Then we need to actually add newitem into the gnonlin timeline
        if not self.producer.scheduleItem(newitem):
            self.debug("Failed to schedule item, unlinking")
            # Failed to schedule it.
            self.unlinkItem(newitem)
            return None

        return newitem

    def unlinkItem(self, item):
        if item.prev:
            item.prev.next = item.next
        else:
            self.items = item.next

        if item.next:
            item.next.prev = item.prev


class PlaylistParser(object, log.Loggable):
    logCategory = 'playlist-parse'

    def __init__(self, playlist):
        self.playlist = playlist

        self._pending_items = []
        self._discovering = False
        self._discovering_blocked = 0

        self._baseDirectory = None

    def setBaseDirectory(self, baseDir):
        if not baseDir.endswith('/'):
            baseDir = baseDir + '/'
        self._baseDirectory = baseDir

    def blockDiscovery(self):
        """
        Prevent playlist parser from running discoverer on any pending
        playlist entries. Multiple subsequent invocations will require
        the same corresponding number of calls to L{unblockDiscovery}
        to resume discovery.
        """
        self._discovering_blocked += 1
        self.debug('  blocking discovery: %d' % self._discovering_blocked)

    def unblockDiscovery(self):
        """
        Resume discovering of any pending playlist entries. If
        L{blockDiscovery} was called multiple times multiple
        invocations of unblockDiscovery will be required to unblock
        the discoverer.
        """
        if self._discovering_blocked > 0:
            self._discovering_blocked -= 1
        self.debug('unblocking discovery: %d' % self._discovering_blocked)
        if self._discovering_blocked < 1:
            self.startDiscovery()

    def startDiscovery(self, doSort=True):
        """
        Initiate discovery of any pending playlist entries.

        @param doSort: should the pending entries be ordered
                       chronologically before initiating discovery
        @type  doSort: bool
        """
        self.log('startDiscovery: discovering: %s, block: %d, pending: %d' %
                 (self._discovering, self._discovering_blocked,
                  len(self._pending_items)))
        if not self._discovering and self._discovering_blocked < 1 \
               and self._pending_items:
            if doSort:
                self._sortPending()
            self._discoverPending()

    def _sortPending(self):
        self.debug('sort pending: %d' % len(self._pending_items))
        if not self._pending_items:
            return
        sortlist = [(elt[1], elt) for elt in self._pending_items]
        sortlist.sort()
        self._pending_items = [elt for (ts, elt) in sortlist]

    def _discoverPending(self):

        def _discovered(disc, is_media):
            self.debug("Discovered! is media: %d mime type %s", is_media,
                disc.mimetype)
            reactor.callFromThread(_discoverer_done, disc, is_media)

        def _discoverer_done(disc, is_media):
            if is_media:
                self.debug("Discovery complete, media found")
                # FIXME: does item exist because it is popped below ?
                # if so, that's ugly and non-obvious and should be fixed
                uri = "file://" + item[0]
                timestamp = item[1]
                duration = item[2]
                offset = item[3]
                piid = item[4]

                hasA = disc.is_audio
                hasV = disc.is_video
                durationDiscovered = 0
                if hasA and hasV:
                    durationDiscovered = min(disc.audiolength,
                        disc.videolength)
                elif hasA:
                    durationDiscovered = disc.audiolength
                elif hasV:
                    durationDiscovered = disc.videolength
                if not duration or duration > durationDiscovered:
                    duration = durationDiscovered

                if duration + offset > durationDiscovered:
                    offset = 0

                if duration > 0:
                    self.playlist.addItem(piid, timestamp, uri,
                        offset, duration, hasA, hasV)
                else:
                    self.warning("Duration of item is zero, not adding")
            else:
                self.warning("Discover failed to find media in %s", item[0])

            # We don't want to burn too much cpu discovering all the files;
            # this throttles the discovery rate to a reasonable level
            self.debug("Continuing on to next file in one second")
            reactor.callLater(1, self._discoverPending)

        if not self._pending_items:
            self.debug("No more files to discover")
            self._discovering = False
            return

        if self._discovering_blocked > 0:
            self.debug("Discovering blocked: %d" % self._discovering_blocked)
            self._discovering = False
            return

        self._discovering = True

        item = self._pending_items.pop(0)

        self.debug("Discovering file %s", item[0])
        disc = discoverer.Discoverer(item[0])

        disc.connect('discovered', _discovered)
        disc.discover()

    def addItemToPlaylist(self, filename, timestamp, duration, offset, piid):
        # We only want to add it if it's plausibly schedulable.
        end = timestamp
        if duration is not None:
            end += duration
        if end < time.time() * gst.SECOND:
            self.debug("Early-out: ignoring add for item in past")
            return

        if filename[0] != '/' and self._baseDirectory:
            filename = self._baseDirectory + filename

        self._pending_items.append((filename, timestamp, duration, offset,
            piid))

        # Now launch the discoverer for any pending items
        self.startDiscovery()


class PlaylistXMLParser(PlaylistParser):
    logCategory = 'playlist-xml'

    def parseData(self, data):
        """
        Parse playlist XML document data
        """
        fileHandle = StringIO(data)
        self.parseFile(fileHandle)

    def replaceFile(self, file, piid):
        self.playlist.removeItems(piid)
        self.parseFile(file, piid)

    def parseFile(self, file, piid=None):
        """
        Parse a playlist file. Adds the contents of the file to the existing
        playlist, overwriting any existing entries for the same time period.
        """
        parser = fxml.Parser()

        root = parser.getRoot(file)

        node = root.documentElement
        self.debug("Parsing playlist from file %s", file)
        if node.nodeName != 'playlist':
            raise fxml.ParserError("Root node is not 'playlist'")

        self.blockDiscovery()
        try:
            for child in node.childNodes:
                if child.nodeType == Node.ELEMENT_NODE and \
                        child.nodeName == 'entry':
                    self.debug("Parsing entry")
                    self._parsePlaylistEntry(parser, child, piid)
        finally:
            self.unblockDiscovery()

    # A simplified private version of this code from fxml without the
    # undesirable unicode->str conversions.

    def _parseAttributes(self, node, required, optional):
        out = []
        for k in required:
            if node.hasAttribute(k):
                out.append(node.getAttribute(k))
            else:
                raise fxml.ParserError("Missing required attribute %s" % k)

        for k in optional:
            if node.hasAttribute(k):
                out.append(node.getAttribute(k))
            else:
                out.append(None)
        return out

    def _parsePlaylistEntry(self, parser, entry, piid):
        mandatory = ['filename', 'time']
        optional = ['duration', 'offset']

        (filename, timestamp, duration, offset) = self._parseAttributes(
            entry, mandatory, optional)

        if duration is not None:
            duration = int(float(duration) * gst.SECOND)
        if offset is None:
            offset = 0
        offset = int(offset) * gst.SECOND

        timestamp = self._parseTimestamp(timestamp)

        # Assume UTF-8 filesystem.
        filename = filename.encode("UTF-8")

        self.addItemToPlaylist(filename, timestamp, duration, offset, piid)

    def _parseTimestamp(self, ts):
        # Take TS in YYYY-MM-DDThh:mm:ss.ssZ format, return timestamp in
        # nanoseconds since the epoch

        # time.strptime() doesn't handle the fractional seconds part. We ignore
        # it entirely, after verifying that it has the right format.
        tsmain, trailing = ts[:-4], ts[-4:]
        if trailing[0] != '.' or trailing[3] != 'Z' or \
                not trailing[1].isdigit() or not trailing[2].isdigit():
            raise fxml.ParserError("Invalid timestamp %s" % ts)
        formatString = "%Y-%m-%dT%H:%M:%S"

        try:
            timestruct = time.strptime(tsmain, formatString)
            return int(calendar.timegm(timestruct) * gst.SECOND)
        except ValueError:
            raise fxml.ParserError("Invalid timestamp %s" % ts)
