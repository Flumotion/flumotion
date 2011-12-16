# -*- Mode: Python; test-case-name: flumotion.test.test_component_providers -*-
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

import datetime
import cgi

from twisted.internet import defer, protocol, reactor
from twisted.python.util import InsensitiveDict
from twisted.web import http

from flumotion.common import log
from flumotion.common import errors
from flumotion.component.misc.httpserver.httpcached import common
from flumotion.component.misc.httpserver.httpcached import http_utils


LOG_CATEGORY = "stream-provider"

USER_AGENT = "FlumotionClient/0.1"


def ts2str(ts):
    if ts:
        return datetime.datetime.fromtimestamp(ts).isoformat()
    return "???"


class StreamInfo(object):
    """
    Provides information about a stream in a standard way.
    The information is retrieved by parsing HTTP headers.
    """

    def __init__(self, headers):
        self.expires = None
        self.mtime = None
        self.length = 0
        self.start = 0
        self.size = 0
        self.mimeType = None

        headers = InsensitiveDict(headers)

        encoding = headers.get("Transfer-Encoding", None)
        if encoding == 'chunked':
            raise errors.FlumotionError("Chunked transfer not supported")

        expires = headers.get("Expires", None)
        if expires is not None:
            try:
                self.expires = http.stringToDatetime(expires)
            except:
                self.expires = 0

        lastmod = headers.get("Last-Modified", None)
        if lastmod is not None:
            self.mtime = http.stringToDatetime(lastmod)

        range = headers.get("Content-Range", None)
        length = headers.get("Content-Length", None)
        if range is not None:
            start, end, total = http.parseContentRange(range)
            self.start = start
            self.length = total
            if length is not None:
                self.size = int(length)
            else:
                self.size = end - start
        elif length is not None:
            self.length = int(length)
            self.size = int(length)
        else:
            raise errors.FlumotionError("Can't get length/size from headers",
                                        headers)

        ctype = headers.get("Content-Type", None)
        if ctype is not None:
            self.mimeType, _pdict = cgi.parse_header(ctype)


class StreamRequester(log.Loggable):
    """
    Allows retrieval of data streams using HTTP 1.0.
    """

    logCategory = LOG_CATEGORY

    def __init__(self, connTimeout=0, idleTimeout=0):
        self.connTimeout = connTimeout
        self.idleTimeout = idleTimeout

    def retrieve(self, consumer, url, proxyAddress=None, proxyPort=None,
                 ifModifiedSince=None, ifUnmodifiedSince=None,
                 start=None, size=None):
        self.log("Requesting %s%s%s%s%s%s",
                 size and (" %d bytes" % size) or "",
                 start and (" starting at %d" % start) or "",
                 (size or start) and " from " or "",
                 url.toString(),
                 ifModifiedSince and (" if modified since %s"
                                      % ts2str(ifModifiedSince)) or "",
                 ifUnmodifiedSince and (" if not modified since %s"
                                        % ts2str(ifUnmodifiedSince)) or "")

        getter = StreamGetter(consumer, url,
                              ifModifiedSince, ifUnmodifiedSince,
                              start, size, self.idleTimeout)
        getter.connect(proxyAddress, proxyPort, self.connTimeout)
        return getter


class StreamGetter(protocol.ClientFactory, http.HTTPClient, log.Loggable):
    """
    Retrieves a stream using HTTP 1.0.

    This class is at the same time a Factory and a Protocol,
    this can be done because it's a client and in twisted
    client factories only create on protocol.

    The outcome, the stream info and stream data is forwarded
    to a common.StreamConsumer instance given at creating time.

    It supports range requests and some conditional request types
    (ifModified and ifUnmodified).
    """

    logCategory = LOG_CATEGORY

    HTTP_METHOD = 'GET'

    host = None
    port = None

    def __init__(self, consumer, url,
                 ifModifiedSince=None, ifUnmodifiedSince=None,
                 start=None, size=None, timeout=0):
        self.consumer = consumer
        self.url = url

        self.ifModifiedSince = ifModifiedSince
        self.ifUnmodifiedSince = ifUnmodifiedSince

        self.start = start
        self.size = size
        self.timeout = timeout

        self.headers = {}
        self.peer = None
        self.status = None
        self.info = None

        self._connected = False
        self._canceled = False
        self._remaining = None
        self._idlecheck = None

        self.logName = common.log_id(self) # To be able to track the instance

    def __repr__(self):
        return "<%s: %s>" % (type(self).__name__, self.url)

    ### Public Methods ###

    def connect(self, proxyAddress=None, proxyPort=None, timeout=0):
        assert not self._connected, "Already connected"
        self._connected = True
        url = self.url
        self.host = proxyAddress or url.hostname
        self.port = proxyPort or url.port
        if url.scheme != 'http':
            msg = "URL scheme %s not implemented" % url.scheme
            self._serverError(common.NOT_IMPLEMENTED, msg)
        else:
            self.log("Connecting to %s:%s for %s",
                     self.host, self.port, self.url)
            reactor.connectTCP(self.host, self.port, self, timeout)

    def pause(self):
        if not self.paused and self.transport is not None:
            self.pauseProducing()
            self.log("Request paused for %s", self.url)

    def resume(self):
        if self.paused and self.transport is not None:
            self.resumeProducing()
            self.log("Request resumed for %s", self.url)

    def cancel(self):
        if self._connected and self.transport is not None:
            self.transport.loseConnection()
        self._cancelIdleCheck()
        self.log("Request canceled for %s", self.url)
        self._canceled = True

    ### Overridden Methods ###

    def buildProtocol(self, addr):
        assert self.peer is None, "Protocol already built"
        self.peer = addr
        return self

    def clientConnectionFailed(self, connector, reason):
        self._serverError(common.SERVER_UNAVAILABLE, reason.getErrorMessage())

    def connectionMade(self):
        self.log("Connection made for %s", self.url)
        self.sendCommand(self.HTTP_METHOD, self.url.location)
        self.sendHeader('Host', self.url.host)
        self.sendHeader('User-Agent', USER_AGENT)
        self.sendHeader('Connection', "close") # Pipeline not yet supported

        if self.ifModifiedSince:
            datestr = http.datetimeToString(self.ifModifiedSince)
            self.sendHeader('If-Modified-Since', datestr)

        if self.ifUnmodifiedSince:
            datestr = http.datetimeToString(self.ifUnmodifiedSince)
            self.sendHeader('If-Unmodified-Since', datestr)

        if self.start or self.size:
            start = self.start or 0
            end = (self.size and (start + self.size - 1)) or None
            rangeSpecs = "bytes=%s-%s" % (start, end or "")
            self.sendHeader('Range', rangeSpecs)

        self.endHeaders()

        self._resetIdleCheck()

    def connectionLost(self, reason):
        self.log("Connection lost for %s", self.url)
        self.handleResponseEnd()
        if not self._canceled:
            self._serverError(common.SERVER_DISCONNECTED,
                              reason.getErrorMessage())

    def handleStatus(self, version, status_str, message):
        self._keepActive()
        status = int(status_str)
        self.status = status

        if status in (http.OK, http.NO_CONTENT, http.PARTIAL_CONTENT):
            return

        if status == http.REQUESTED_RANGE_NOT_SATISFIABLE:
            self._serverError(common.RANGE_NOT_SATISFIABLE,
                              "HTTP range not satisfiable")
        if status == http.NOT_MODIFIED:
            self._conditionFail(common.STREAM_NOT_MODIFIED,
                                "Stream not modified")
        elif status == http.PRECONDITION_FAILED:
            self._conditionFail(common.STREAM_MODIFIED, "Stream Modified")
        elif status == http.NOT_FOUND:
            self._streamNotAvailable(common.STREAM_NOTFOUND,
                                     "Resource Not Found")
        elif status == http.FORBIDDEN:
            self._streamNotAvailable(common.STREAM_FORBIDDEN,
                                     "Resource Forbidden")
        if status in (http.MOVED_PERMANENTLY, http.FOUND):
            self._serverError(common.NOT_IMPLEMENTED,
                              "HTTP redirection not supported")
        else:
            self._serverError(common.NOT_IMPLEMENTED,
                              "Unsupported HTTP response: %s (%s)"
                              % (message, status))

    def handleHeader(self, key, val):
        self._keepActive()
        self.headers[key] = val

    def handleEndHeaders(self):
        self._keepActive()
        self.info = StreamInfo(self.headers)
        self._remaining = self.info.size

        if self.size and self.size < self.info.size:
            self.warning("Response size bigger than the requested size, "
                         "expecting %s bytes and response length is %s",
                         self.size, self.info.size)
            # We asked for a range but the proxy answered with the whole
            # file. We're only interested on the first self.size bytes.
            self._remaining = self.size

        self._onInfo(self.info)

    def handleResponsePart(self, data):
        self._keepActive()
        size = len(data)

        if self._remaining > 0 and self._remaining < size:
            self.warning("More than %s bytes have been received",
                         self.info.size)

        # Keep just the bytes needed to fulfill the original range request,
        # discard the rest because they will be in the next request after
        # this one is cancelled.
        if self._remaining < size:
            data = data[:self._remaining]
            self._remaining = 0
            self._onData(data)
            self.cancel()
        else:
            self._remaining -= size
            self._onData(data)

    def handleResponseEnd(self):
        if self.info is not None:
            if self._remaining == 0:
                self.log("Request done, got %d bytes starting at %d from %s, "
                         "last modified on %s", self.info.size,
                         self.info.start, self.url.toString(),
                         ts2str(self.info.mtime))
                self._streamDone()
                return
        if self.info:
            self.log("Incomplete request, missing %d bytes from the expected "
                     "%d bytes starting at %d from %s", self._remaining,
                     self.info.size, self.info.start, self.url.toString())
        else:
            self.log("Incomplete request %s", self.url.toString())

    def sendCommand(self, command, path):
        # We want HTTP/1.1 for conditional GET and range requests
        self.transport.write('%s %s HTTP/1.1\r\n' % (command, path))

    ### Private Methods ###

    def _keepActive(self):
        self._updateCount += 1

    def _resetIdleCheck(self):
        self._cancelIdleCheck()
        self._idlecheck = reactor.callLater(self.timeout, self._onIdleCheck)

    def _cancelIdleCheck(self):
        if self._idlecheck:
            self._idlecheck.cancel()
        self._idlecheck = None
        self._updateCount = 0

    def _onIdleCheck(self):
        self._idlecheck = None
        if not self._updateCount:
            self._onTimeout()
        else:
            self._resetIdleCheck()

    def _onTimeout(self):
        self._idlecheck = None
        self._serverError(common.SERVER_TIMEOUT, "Server timeout")

    def _cancel(self):
        self._cancelIdleCheck()
        if self.consumer:
            if self.transport:
                self.transport.loseConnection()
            self.consumer = None

    def _serverError(self, code, message):
        if self.consumer:
            self.consumer.serverError(self, code, message)
            self._cancel()

    def _conditionFail(self, code, message):
        if self.consumer:
            self.consumer.conditionFail(self, code, message)
            self._cancel()

    def _streamNotAvailable(self, code, message):
        if self.consumer:
            self.consumer.streamNotAvailable(self, code, message)
            self._cancel()

    def _onInfo(self, info):
        if self.consumer:
            self.consumer.onInfo(self, info)

    def _onData(self, data):
        if self.consumer:
            self.consumer.onData(self, data)

    def _streamDone(self):
        if self.consumer:
            self.consumer.streamDone(self)
            self._cancel()


if __name__ == "__main__":
    import sys

    def addarg(d, a):
        k, v = a.split('=', 1)
        if v == 'None':
            d[k] = None
        try:
            d[k] = int(v)
        except:
            d[k] = v


    kwargs = {}
    for a in sys.argv[1:]:
        addarg(kwargs, a)

    url = kwargs.pop('url')

    class DummyConsumer(object):

        def serverError(self, getter, code, message):
            print "Failure: %s (%d)" % (message, code)
            reactor.stop()

        def conditionFail(self, getter, code, message):
            print "Condition: %s (%d)" % (message, code)
            reactor.stop()

        def streamNotAvailable(self, getter, code, message):
            print message
            reactor.stop()

        def streamDone(self, getter):
            print "Finished"
            reactor.stop()

        def onInfo(self, getter, info):
            exp = info.expires and http.datetimeToString(info.expires)
            mod = info.mtime and http.datetimeToString(info.mtime)
            print "Found, Exp:", exp, "Mod:", mod
            print "Len:", info.length, "Start:", \
                   info.start, "Size:", info.size

        def onData(self, getter, data):
            #print "Data (%d)" % len(data)
            pass


    consumer = DummyConsumer()
    requester = StreamRequester(5000, 5000)
    requester.retrieve(consumer, http_utils.Url.fromString(url), **kwargs)
    reactor.run()
