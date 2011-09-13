# -*- Mode: Python -*-
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

from twisted.internet import reactor
from twisted.web import server

from flumotion.component.common.streamer.streamer import \
        Streamer, Stats as Statistics


class Stats(Statistics):

    def __init__(self, request):
        Statistics.__init__(self)
        self.request = request

    def getBytesSent(self):
        return self.request.getBytesSent()

    def getBytesReceived(self):
        return self.request.getBytesReceived()


class LoggableRequest(server.Request):

    def __init__(self, channel, queued):
        server.Request.__init__(self, channel, queued)
        now = time.time()
        self._startTime = now
        self._completionTime = now
        self._bytesWritten = 0L

    def write(self, data):
        server.Request.write(self, data)
        size = len(data)
        self._bytesWritten += size

    def requestCompleted(self, fd):
        server.Request.requestCompleted(self, fd)
        if self._completionTime is None:
            self._completionTime = time.time()

    def getDuration(self):
        return (self._completionTime or time.time()) - self._startTime

    def getBytesSent(self):
        return self._bytesWritten


class Site(server.Site):
    requestFactory = LoggableRequest

    def __init__(self, resource):
        server.Site.__init__(self, resource)


class FragmentedStreamer(Streamer, Stats):
    DEFAULT_MIN_WINDOW = 2
    DEFAULT_MAX_WINDOW = 5
    DEFAULT_SECRET_KEY = 'aR%$w34Y=&08gFm%&!s8080'
    DEFAULT_SESSION_TIMEOUT = 30

    logCategory = 'fragmented-streamer'
    siteClass = Site

    def init(self):
        self.debug("HTTP live fragmented streamer initialising")

    def do_pipeline_playing(self):
        # The component must stay 'waiking' until it receives at least
        # the number of segments defined by the min-window property
        pass

    def updateBytesReceived(self, length):
        self.resource.bytesReceived += length

    def __repr__(self):
        return '<FragmentedStreamer (%s)>' % self.name

    def _connectSinkSignals(self):
        self.sink.get_pad("sink").add_buffer_probe(self._sink_pad_probe, None)

    ### START OF THREAD-AWARE CODE (called from non-reactor threads)

    def _sink_pad_probe(self, pad, buffer, none):
        reactor.callFromThread(self.updateBytesReceived, len(buffer.data))
        return True

    ### END OF THREAD-AWARE CODE
