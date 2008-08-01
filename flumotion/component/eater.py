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

import time

from twisted.internet import reactor

from flumotion.common import componentui

__version__ = "$Rev$"


class Eater:
    """
    This class groups eater-related information as used by a Feed Component.

    @ivar eaterAlias:  the alias of this eater (e.g. "default", "video",
                       ...)
    @ivar feedId:  id of the feed this is eating from
    @ivar uiState: the serializable UI State for this eater
    """

    def __init__(self, eaterAlias, eaterName):
        self.eaterAlias = eaterAlias
        self.eaterName = eaterName
        self.feedId = None
        self.fd = None
        self.elementName = 'eater:' + eaterAlias
        self.depayName = self.elementName + '-depay'
        self.setPadMonitor(None)
        self.uiState = componentui.WorkerComponentUIState()
        self.uiState.addKey('eater-alias')
        self.uiState.set('eater-alias', eaterAlias)
        self.uiState.addKey('eater-name')
        self.uiState.set('eater-name', eaterName)
        # dict for the current connection
        connectionDict = {
            "feed-id": None,
            "time-timestamp-discont": None,
            "timestamp-timestamp-discont": 0.0,  # ts of buffer after discont,
                                                 # in float seconds
            "last-timestamp-discont": 0.0,
            "total-timestamp-discont": 0.0,
            "count-timestamp-discont": 0,
            "time-offset-discont": None,
            "offset-offset-discont": 0, # offset of buffer
                                        # after discont
            "last-offset-discont": 0,
            "total-offset-discont": 0,
            "count-offset-discont": 0}
        self.uiState.addDictKey('connection', connectionDict)

        for key in (
            'last-connect',           # last client connection, in epoch sec
            'last-disconnect',        # last client disconnect, in epoch sec
            'total-connections',      # number of connections by this client
            'count-timestamp-discont', # number of timestamp disconts seen
            'count-offset-discont',    # number of timestamp disconts seen
            ):
            self.uiState.addKey(key, 0)
        for key in (
            'total-timestamp-discont', # total timestamp discontinuity
            'total-offset-discont',    # total offset discontinuity
            ):
            self.uiState.addKey(key, 0.0)
        self.uiState.addKey('fd', None)

    def __repr__(self):
        return '<Eater %s %s>' % (self.eaterAlias,
                                  (self.feedId and '(disconnected)'
                                   or ('eating from %s' % self.feedId)))

    def connected(self, fd, feedId, when=None):
        """
        The eater has been connected.
        Update related stats.
        """
        if not when:
            when = time.time()

        self.feedId = feedId
        self.fd = fd

        self.uiState.set('last-connect', when)
        self.uiState.set('fd', fd)
        self.uiState.set('total-connections',
            self.uiState.get('total-connections', 0) + 1)

        self.uiState.setitem("connection", 'feed-id', feedId)
        self.uiState.setitem("connection", "count-timestamp-discont", 0)
        self.uiState.setitem("connection", "time-timestamp-discont", None)
        self.uiState.setitem("connection", "last-timestamp-discont", 0.0)
        self.uiState.setitem("connection", "total-timestamp-discont", 0.0)
        self.uiState.setitem("connection", "count-offset-discont", 0)
        self.uiState.setitem("connection", "time-offset-discont", None)
        self.uiState.setitem("connection", "last-offset-discont", 0)
        self.uiState.setitem("connection", "total-offset-discont", 0)

    def disconnected(self, when=None):
        """
        The eater has been disconnected.
        Update related stats.
        """
        if not when:
            when = time.time()

        def updateUIState():
            self.uiState.set('last-disconnect', when)
            self.fd = None
            self.uiState.set('fd', None)

        reactor.callFromThread(updateUIState)

    def setPadMonitor(self, monitor):
        self._padMonitor = monitor

    def isActive(self):
        return self._padMonitor and self._padMonitor.isActive()

    def addWatch(self, setActive, setInactive):
        self._padMonitor.addWatch(lambda _: setActive(self.eaterAlias),
                                  lambda _: setInactive(self.eaterAlias))

    def timestampDiscont(self, seconds, timestamp):
        """
        @param seconds:   discont duration in seconds
        @param timestamp: GStreamer timestamp of new buffer, in seconds.

        Inform the eater of a timestamp discontinuity.
        This is called from a bus message handler, so in the main thread.
        """
        uiState = self.uiState

        c = uiState.get('connection') # dict
        uiState.setitem('connection', 'count-timestamp-discont',
            c.get('count-timestamp-discont', 0) + 1)
        uiState.set('count-timestamp-discont',
            uiState.get('count-timestamp-discont', 0) + 1)

        uiState.setitem('connection', 'time-timestamp-discont', time.time())
        uiState.setitem('connection', 'timestamp-timestamp-discont', timestamp)
        uiState.setitem('connection', 'last-timestamp-discont', seconds)
        uiState.setitem('connection', 'total-timestamp-discont',
            c.get('total-timestamp-discont', 0) + seconds)
        uiState.set('total-timestamp-discont',
            uiState.get('total-timestamp-discont', 0) + seconds)

    def offsetDiscont(self, units, offset):
        """
        Inform the eater of an offset discontinuity.
        This is called from a bus message handler, so in the main thread.
        """
        uiState = self.uiState

        c = uiState.get('connection') # dict
        uiState.setitem('connection', 'count-offset-discont',
            c.get('count-offset-discont', 0) + 1)
        uiState.set('count-offset-discont',
            uiState.get('count-offset-discont', 0) + 1)

        uiState.setitem('connection', 'time-offset-discont', time.time())
        uiState.setitem('connection', 'offset-offset-discont', offset)
        uiState.setitem('connection', 'last-offset-discont', units)
        uiState.setitem('connection', 'total-offset-discont',
            c.get('total-offset-discont', 0) + units)
        uiState.set('total-offset-discont',
            uiState.get('total-offset-discont', 0) + units)
