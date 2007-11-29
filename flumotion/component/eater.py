# -*- Mode: Python; test-case-name: flumotion.test.test_feedcomponent010 -*-
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
        self.uiState.addKey('eaterAlias')
        self.uiState.set('eaterAlias', eaterAlias)
        self.uiState.addKey('eaterName')
        self.uiState.set('eaterName', eaterName)
        # dict for the current connection
        connectionDict = {
            "feedId":                None,
            "timeTimestampDiscont":  None,
            "timestampTimestampDiscont":  0.0,  # ts of buffer after discont,
                                                # in float seconds
            "lastTimestampDiscont":  0.0,
            "totalTimestampDiscont": 0.0,
            "countTimestampDiscont": 0,
            "timeOffsetDiscont":     None,
            "offsetOffsetDiscont":   0,         # offset of buffer after discont
            "lastOffsetDiscont":     0,
            "totalOffsetDiscont":    0,
            "countOffsetDiscont":    0,

         }
        self.uiState.addDictKey('connection', connectionDict)

        for key in (
            'lastConnect',           # last client connection, in epoch seconds
            'lastDisconnect',        # last client disconnect, in epoch seconds
            'totalConnections',      # number of connections made by this client
            'countTimestampDiscont', # number of timestamp disconts seen
            'countOffsetDiscont',    # number of timestamp disconts seen
            ):
            self.uiState.addKey(key, 0)
        for key in (
            'totalTimestampDiscont', # total timestamp discontinuity
            'totalOffsetDiscont',    # total offset discontinuity
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

        self.uiState.set('lastConnect', when)
        self.uiState.set('fd', fd)
        self.uiState.set('totalConnections',
            self.uiState.get('totalConnections', 0) + 1)

        self.uiState.setitem("connection", 'feedId', feedId)
        self.uiState.setitem("connection", "countTimestampDiscont", 0)
        self.uiState.setitem("connection", "timeTimestampDiscont",  None)
        self.uiState.setitem("connection", "lastTimestampDiscont",  0.0)
        self.uiState.setitem("connection", "totalTimestampDiscont", 0.0)
        self.uiState.setitem("connection", "countOffsetDiscont",    0)
        self.uiState.setitem("connection", "timeOffsetDiscont",     None)
        self.uiState.setitem("connection", "lastOffsetDiscont",     0)
        self.uiState.setitem("connection", "totalOffsetDiscont",    0)

    def disconnected(self, when=None):
        """
        The eater has been disconnected.
        Update related stats.
        """
        if not when:
            when = time.time()

        def updateUIState():
            self.uiState.set('lastDisconnect', when)
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
        uiState.setitem('connection', 'countTimestampDiscont',
            c.get('countTimestampDiscont', 0) + 1)
        uiState.set('countTimestampDiscont',
            uiState.get('countTimestampDiscont', 0) + 1)

        uiState.setitem('connection', 'timeTimestampDiscont', time.time())
        uiState.setitem('connection', 'timestampTimestampDiscont', timestamp)
        uiState.setitem('connection', 'lastTimestampDiscont', seconds)
        uiState.setitem('connection', 'totalTimestampDiscont',
            c.get('totalTimestampDiscont', 0) + seconds)
        uiState.set('totalTimestampDiscont',
            uiState.get('totalTimestampDiscont', 0) + seconds)

    def offsetDiscont(self, units, offset):
        """
        Inform the eater of an offset discontinuity.
        This is called from a bus message handler, so in the main thread.
        """
        uiState = self.uiState

        c = uiState.get('connection') # dict
        uiState.setitem('connection', 'countOffsetDiscont',
            c.get('countOffsetDiscont', 0) + 1)
        uiState.set('countOffsetDiscont',
            uiState.get('countOffsetDiscont', 0) + 1)

        uiState.setitem('connection', 'timeOffsetDiscont', time.time())
        uiState.setitem('connection', 'offsetOffsetDiscont', offset)
        uiState.setitem('connection', 'lastOffsetDiscont', units)
        uiState.setitem('connection', 'totalOffsetDiscont',
            c.get('totalOffsetDiscont', 0) + units)
        uiState.set('totalOffsetDiscont',
            uiState.get('totalOffsetDiscont', 0) + units)
