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

import sys
import socket
import time
import urllib2

import gobject

from flumotion.common import log
from flumotion.tester import client

__version__ = "$Rev$"


class HTTPClient(gobject.GObject, log.Loggable):
    """
    Base class for HTTP clients.
    """

    __gsignals__ = {
        'stopped': (gobject.SIGNAL_RUN_FIRST, None, (int, int)),
    }

    logCategory = "httpclient"

    def __init__(self, id, url):
        """
        @param id: id of the client.
        @param url: URL to open.
        @type url: string.
        """
        self.__gobject_init__()
        self._url = url
        self._id = id
        self._handle = None
        self._stop_time = 0 # delta to start time
        self._stop_size = 0

    def next_read_time(self):
        """
        Calculate the next time to read.

        @rtype: float
        @returns: next read time in seconds since epoch.
        """
        raise Exception("next_read_time needs to be implemented by a subclass")

    def read_size(self):
        """
        calculate and return the size of the current read'
        """

    def set_stop_time(self, stop_time):
        """
        Set a maximum time to run for.  If a client reaches this,
        it means the run was successful.
        """
        self._stop_time = stop_time

    def set_stop_size(self, stop_size):
        """
        Set a maximum size to read.  If a client reaches this,
        it means the run was successful.
        """
        self._stop_size = stop_size

    def open(self):
        'open the connection'
        self._start_time = time.time()
        self._bytes = 0
        try:
            self._handle = urllib2.urlopen(self._url)
        except urllib2.HTTPError, error:
            self.warning("%4d: connect: HTTPError: code %s, msg %s" %
                (self._id, error.code, error.msg))
            if error.code == -1:
                self.emit('stopped', self._id, client.STOPPED_INTERNAL_ERROR)
                return
            self.emit('stopped', self._id, client.STOPPED_CONNECT_ERROR)
            return
        except urllib2.URLError, exception:
            code = None
            #try:
            code = exception.reason[0]
            #except:
            #    print "Unhandled exception: %s" % exception
            #    self.emit('stopped')
            #    return

            if code == 111:
                self.warning("%4d: connection refused" % self._id)
                self.emit('stopped', self._id, client.STOPPED_REFUSED)
                return
            else:
                self.warning("%4d: unhandled URLError with code %d" % (
                    self._id, code))
                self.emit('stopped', self._id, client.STOPPED_CONNECT_ERROR)
                return
        except socket.error, (code, msg):
            if code == 104:
                # Connection reset by peer
                self.warning("%4d: %s" % (self._id, msg))
                self.emit('stopped', self._id, client.STOPPED_CONNECT_ERROR)
                return
            else:
                self.warning("%4d: unhandled socket.error with code %d" % (
                    self._id, code))
                self.emit('stopped', self._id, self.stopped_CONNECT_ERROR)
                return
        if not self._handle:
            self.warning("%4d: didn't get fd from urlopen" % self._id)
            self.emit('stopped', self._id, self.stopped_INTERNAL_ERROR)
            return

        delta = self.next_read_time() - self._start_time
        timeout = int(delta * 1000)
        gobject.timeout_add(timeout, self.read)

    def read(self):
        size = self.read_size()
        if size == 0:
            self.warning("%4d: read_size returns 0, wrong scheduling")
            self.close(client.STOPPED_INTERNAL_ERROR)
            return False

        self.log("%4d: read(%d)" % (self._id, size))
        try:
            data = self._handle.read(size)
        except KeyboardInterrupt:
            sys.exit(1)
        # possible AssertionError in httplib.py, line 1180, in read
        # assert not self._line_consumed and self._line_left
        except AssertionError:
            self.warning("httplib assertion error, closing")
            self.close(client.STOPPED_INTERNAL_ERROR)
            return False

        if len(data) == 0:
            self.warning("zero bytes read, closing")
            self.close(client.STOPPED_READ_ERROR)
            return False

        #print "%4d: %d bytes read" % (self._id, len(data))
        self._bytes += len(data)
        #if not self.verify(data):
        #    print "OH MY GOD ! THIEF !"

        now = time.time()

        # handle exit conditions
        if self._stop_time:
            if now - self._start_time > self._stop_time:
                self.warning("%4d: stop time reached, closing" % self._id)
                self._handle.close()
                self.close(client.STOPPED_SUCCESS)
                return False
        if self._stop_size:
            if self._bytes > self._stop_size:
                self.info("%4d: stop size reached, closing" % self._id)
                self._handle.close()
                self.close(client.STOPPED_SUCCESS)
                return False

        # schedule next read
        delta = self.next_read_time() - time.time()
        timeout = int(delta * 1000)
        if timeout < 0:
            timeout = 0
        #print "%4d: timeout to next read: %d ms" % (self._id, timeout)
        gobject.timeout_add(timeout, self.read)

        #calculate stats
        rate = self._bytes / (now - self._start_time) / 1024.0
        #print "%d: %f: read: %d bytes, nominal actual rate: %f" %
        # (self._id, now, self._bytes, rate)
        return False

    def close(self, reason):
        'close the connection'
        self.emit('stopped', self._id, reason)


class HTTPClientStatic(HTTPClient):
    """
    HTTP client reading at regular intervals with a fixed read size and
    a fixed rate in KByte/sec.
    """

    logCategory = "h-c-s"

    def __init__(self, id, url, rate = 5000, readsize = 1024):
        self._rate = rate
        self._readsize = readsize
        HTTPClient.__init__(self, id, url)
        self.debug("Creating client %s with rate %d and readsize %d" %
            (id, rate, readsize))

    def next_read_time(self):
        'calculate the next time we want to read.  Could be in the past.'
            # calculate the next byte count
        next_byte_count = self._bytes + self._readsize

        # calculate the elapsed time corresponding to this read moment
        time_delta = next_byte_count / (float(self._rate))

        ret = self._start_time + time_delta
        self.log("%4d: next read time in %f secs" % (self._id, time_delta))
        return ret

    def read_size(self):
        return self._readsize

lastbyte = {}


def verify(client, data):
    if not client in lastbyte:
        next = ord(data[0])
    else:
        next = ord(lastbyte[client]) + 1
        if next > 255:
            next = 0
    #print " next byte: %x" % next
    print len(data)

    import struct
    # create a range of integer values starting at next and as long as the data
    numbers = range(next, next + len(data))
    # map a mod on to it so they get truncated to the pattern
    bytes = map(lambda x: x % 256, numbers)

    buffer = struct.pack("B" * len(bytes), *bytes)
    #print "comparing buffer to data: %d - %d" % (len(buffer), len(data))
    #print "comparing buffer to data: %d - %d" % (ord(buffer[0]), ord(data[0]))
    #print "comparing buffer to data: %d - %d" % (ord(buffer[-1]),
    #  ord(data[-1]))
    if (buffer != data):
        print "WOAH NELLY !"
        return False
    return True

gobject.type_register(HTTPClient)
gobject.type_register(HTTPClientStatic)
