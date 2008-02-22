# -*- Mode: Python; test-case-name: -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
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

__version__ = "$Rev$"

import time

from flumotion.common import log

from twisted.internet import reactor

"""
Use a token bucket to proxy between a producer (e.g. FileTransfer) and a 
consumer (TCP protocol, etc.), doing rate control.

The bucket has a rate and a maximum level, so a small burst can be permitted.
The initial level can be set to a non-zero value, this is useful to implement
burst-on-connect behaviour.

TODO: This almost certainly only works with producers that work like 
FileTransfer - i.e. they produce data directly in resumeProducing, and ignore
pauseProducing. This is sufficient for our needs right now.
"""

class TokenBucketConsumer(log.Loggable):

    _dripInterval = 0.2 # If we need to wait for more bits in our bucket, wait 
                        # at least this long, to avoid overly frequent small 
                        # writes

    def __init__(self, consumer, maxLevel, fillRate, fillLevel=0):
        self.maxLevel = maxLevel # in bytes
        self.fillRate = fillRate # in bytes per second
        self.fillLevel = fillLevel # in bytes

        self._buffer = "" # TODO: Maybe this should be a list of buffers, or
                          # of (buffer, offset) tuples, so we can avoid copies?
        self._finishing = False # If true, we'll stop once the current buffer
                                # has been sent.

        self._lastDrip = time.time()
        self._dripDC = None

        self.producer = None # we get this in registerProducer.
        self.consumer = consumer

        self.consumer.registerProducer(self, 0)

        self.info("Created TokenBucket with rate %d, initial level %d, "
            "maximum level %d", fillRate, fillLevel, maxLevel)

    def _dripAndTryWrite(self):
        """
        Re-fill our token bucket based on how long it has been since we last
        refilled it.
        Then attempt to write some data.
        """
        self._dripDC = None

        now = time.time()
        elapsed = now - self._lastDrip
        self._lastDrip = now

        bytes = self.fillRate * elapsed
        # Note that this does introduce rounding errors - not particularly
        # important if the drip interval is reasonably high, though. These will
        # cause the actual rate to be lower than the nominal rate.
        self.fillLevel = int(min(self.fillLevel + bytes, self.maxLevel))

        self._tryWrite()

    def _tryWrite(self):
        if self.fillLevel > 0 and len(self._buffer) > 0:
            # If we're permitted to write at the moment, do so.
            buf = self._buffer[:self.fillLevel]
            bytes = len(buf)

            self._buffer = self._buffer[bytes:]

            self.consumer.write(buf)
            self.fillLevel -= bytes

        if len(self._buffer) > 0:
            # If we have data (and we're not already waiting for our next drip
            # interval), wait... this is what actually performs the data
            # throttling.
            if not self._dripDC:
                self._dripDC = reactor.callLater(self._dripInternal, 
                    self._dripAndTryWrite)
        else:
            # No buffer remaining; ask for more data or finish
            if self._finishing:
                self.consumer.finish()
            elif self.producer:
                self.producer.resumeProducing()

    def stopProducing(self):
        if self.producer is not None:
            self.producer.stopProducing()

    def pauseProducing(self):
        pass

    def resumeProducing(self):
        #self.debug("resumeProducing called")
        self._tryWrite()
        
        if not self._buffer and self.producer:
            self.producer.resumeProducing()

    def write(self, data):
        self._buffer += data

        self._tryWrite()

        if self._buffer and not self.fillLevel and self.producer:
            self.producer.pauseProducing()

    def finish(self):
        self._finishing = True

    def registerProducer(self, producer, streaming):
        self.producer = producer

        self.resumeProducing()

    def unregisterProducer(self):
        if self.producer is not None:
            self.producer = None

            self.consumer.unregisterProducer()

