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
from StringIO import StringIO

from xml.dom import Node

from twisted.internet import reactor

from flumotion.common import log, fxml

import singledecodebin

def file_gnl_src(name, uri, caps, start, duration, offset, priority):
    src = singledecodebin.SingleDecodeBin(caps, uri)
    gnlsrc = gst.element_factory_make('gnlsource', name)
    gnlsrc.props.start = start
    gnlsrc.props.duration = duration
    gnlsrc.props.media_start = offset
    gnlsrc.props.media_duration = duration
    gnlsrc.props.priority = priority
    gnlsrc.add(src)

    return gnlsrc

class PlaylistItem(object, log.Loggable):
    def __init__(self, id, timestamp, uri, offset, duration):
        self.id = id
        self.timestamp = timestamp
        self.uri = uri
        self.offset = offset
        self.duration = duration

        # Currently always set to true; later this should come from what the
        # discoverer says.
        self.hasAudio = True
        self.hasVideo = True

        # Audio and video gnlsource objects
        self.vsrc = None
        self.asrc = None

        self.next = None
        self.prev = None

    def setDuration(self, duration):
        self.duration = duration
        if self.asrc:
            self.asrc.props.duration = duration
            self.asrc.props.media_duration = duration
        if self.vsrc:
            self.vsrc.props.duration = duration
            self.vsrc.props.media_duration = duration

    def setTimestamp(self, timestamp):
        self.timestamp = timestamp
        if self.asrc:
            self.asrc.props.start = timestamp
        if self.vsrc:
            self.vsrc.props.start = timestamp

class Playlist(object, log.Loggable):
    def __init__(self, producer):
        """
        Create an initially empty playlist
        """
        self.items = None # PlaylistItem linked list
        self._itemsById = {}

        self.producer = producer

        self._pending_items = []
        self._discovering = False

    def _getCurrentItem(self):
        # TODO: improve this!
        return None

    def removeItems(self, id):
        current = self._getCurrentItem()
            
        items = self._itemsById[id]
        for item in items:
            if (current and item.timestamp < current.timestamp + 
                    current.duration):
                self.debug("Not removing current item!")
                continue
            if item.prev:
                item.prev.next = item.next
            if item.next:
                item.next.prev = item.prev
            self.producer.unscheduleItem(item)

        del self._itemsById[id]
        

    def addItem(self, id, timestamp, uri, offset, duration, hasAudio, hasVideo):
        """
        Add an item to the playlist.
        The duration of previous and this entry may be adjusted to make it fit.
        """
        current = self._getCurrentItem()
        if current and timestamp < current.timestamp + current.duration:
            self.warning("New object at uri %s starts during current object, "
                "cannot add")
            return

        newitem = PlaylistItem(id, timestamp, uri, offset, duration)
        newitem.hasAudio = hasAudio
        newitem.hasVideo = hasVideo

        if id in self._itemsById:
            self._itemsById[id].append(newitem)
        else:
            self._itemsById[id] = [newitem]

        # prev starts strictly before the new item
        # next starts after the new item, and ends after the end of the new item
        prev = next = None
        item = self.items
        while item:
            if item.timestamp < newitem.timestamp:
                prev = item
            else:
                break
            item = item.next

        if item:
            item = item.next
        while item:
            if (item.timestamp + item.duration > newitem.timestamp):
                next = item
                break
            item = item.next

        if prev:
            # Then things between prev and next (next might be None) are to be 
            # deleted. Do so.
            cur = prev.next
            while cur != next:
                self.producer.unscheduleItem(cur)
                cur = cur.next

        # update links.
        if prev:
            prev.next = newitem
            newitem.prev = prev
        else:
            self.items = newitem

        if next:
            newitem.next = next
            next.prev = newitem

        # Duration adjustments -> Reflect into gnonlin timeline
        if prev and prev.timestamp + prev.duration > newitem.timestamp:
            self.debug("Changing duration of previous item from %d to %d", 
                prev.duration, newitem.timestamp - prev.timestamp)
            item.setDuration(newitem.timestamp - prev.timestamp)

        if next and newitem.timestamp + newitem.duration > next.timestamp:
            self.debug("Changing timestamp of next item from %d to %d to fit", 
                newitem.timestamp, newitem.timestamp + newitem.duration)
            ts = newitem.timestamp + newitem.duration
            duration = next.duration - (ts - next.timestamp)
            next.setTimestamp(ts)
            next.setDuration(duration)

        # Then we need to actually add newitem into the gnonlin timeline
        self.producer.scheduleItem(newitem)

    def expireOldEntries(self):
        """
        Delete references to old playlist entries that have passed.
        TODO: is this needed? It's to save memory, but probably not very much 
        memory...
        """
        pass

    def parseData(self, data):
        """
        Parse playlist XML document data
        """
        file = StringIO(data)
        self.parseFile(file)

    def replaceFile(self, file, id):
        self.removeItems(id)
        self.parseFile(file, id)

    def parseFile(self, file, id=None):
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

        for child in node.childNodes:
            if child.nodeType == Node.ELEMENT_NODE and \
                    child.nodeName == 'entry':
                self.debug("Parsing entry")
                self._parsePlaylistEntry(parser, child, id)

        # Now launch the discoverer for any pending items
        if not self._discovering:
            self._discoverPending()

    def _discoverPending(self):
        def _discovered(disc, is_media):
            self.debug("Discovered!")
            reactor.callFromThread(_discoverer_done, disc, is_media)

        def _discoverer_done(disc, is_media):
            if is_media:
                self.debug("Discovery complete, media found")
                uri = "file://" + item[0]
                timestamp = item[1]
                duration = item[2]
                offset = item[3]
                id = item[4]

                hasA = disc.is_audio
                hasV = disc.is_video
                durationDiscovered = min(disc.audiolength, 
                    disc.videolength)
                if not duration or duration > durationDiscovered:
                    duration = durationDiscovered

                if duration + offset > durationDiscovered:
                    offset = 0

                if duration > 0:
                    self.addItem(id, timestamp, uri, offset, duration, 
                        hasA, hasV)
                else:
                    self.warning("Duration of item is zero, not adding")
            else:
                self.warning("Discover failed to find media in %s", item[0])
    
            self.debug("Continuing on to next file")
            self._discoverPending()

        if not self._pending_items:
            self.debug("No more files to discover")
            self._discovering = False
            return

        self._discovering = True
        
        item = self._pending_items.pop(0)

        self.debug("Discovering file %s", item[0])
        disc = discoverer.Discoverer(item[0])

        disc.connect('discovered', _discovered)
        disc.discover()

    def _parsePlaylistEntry(self, parser, entry, id):
        mandatory = ['filename', 'time']
        optional = ['duration', 'offset']

        (filename, timestamp, duration, offset) = parser.parseAttributes(
            entry, mandatory, optional)

        if duration is not None:
            duration = int(float(duration) * gst.SECOND)
        if offset is None:
            offset = 0
        offset = int(offset) * gst.SECOND

        timestamp = self._parseTimestamp(timestamp)

        self._pending_items.append((filename, timestamp, duration, offset, id))

    def _parseTimestamp(self, ts):
        # Take TS in YYYY-MM-DDThh:mm:ssZ format, return timestamp in 
        # nanoseconds since the epoch
        format = "%Y-%m-%dT%H:%M:%SZ"

        try:
            timestruct = time.strptime(ts, format)

            return int(time.mktime(timestruct) * gst.SECOND)
        except ValueError:
            raise fxml.ParserError("Invalid timestamp %s", ts)


