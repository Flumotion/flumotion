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

Consumer calls resumeProducing() on us. In reaction, if the TB has sufficient
bits in it, we call resumeProducing() on our producer parent, and then write() 
that to our consumer. 

Otherwise, we call pauseProducing() on the producer, and unregisterProducer()
on the consumer. Then we schedule a DelayedCall that will refill our bucket,
and then resume production...

"""

class TokenBucket(log.Loggable):

    _dripMinimum = 0.2 # If we need to wait for more bits in our bucket, wait 
                       # at least this long, to avoid overly frequent small 
                       # writes

    def __init__(self, consumer, maxLevel, fillRate, fillLevel=0):
        self.maxLevel = maxLevel # in bytes
        self.fillRate = fillRate # in bytes per second
        self.fillLevel = fillLevel # in bytes

        self._buffer = ""
        self._finishing = False
        self._lastDrip = time.time()
        self._dripDC = None

#        self.producer = producer
        self.producer = None # we get this in registerProducer.
        self.consumer = consumer

        self.consumer.registerProducer(self, 0)

#        self.info("Created TokenBucket with rate %d", fillRate)

    def _dripAndTryWrite(self):
        self._dripDC = None

        now = time.time()
        elapsed = now - self._lastDrip
        self._lastDrip = now

        bytes = self.fillRate * elapsed
 #       self.debug("dripping %d bytes (to max %d) into bucket: %f * %f", bytes, self.maxLevel, self.fillRate, elapsed)
        self.fillLevel = int(min(self.fillLevel + bytes, self.maxLevel))

        self._tryWrite()

    def _tryWrite(self):
  #      self.debug("Trying to write %d bytes, bucket has %d bytes", len(self._buffer), self.fillLevel)

        if self.fillLevel > 0 and len(self._buffer) > 0:
            buf = self._buffer[:self.fillLevel]
            bytes = len(buf)

            self._buffer = self._buffer[bytes:]

            self.consumer.write(buf)
            self.fillLevel -= bytes

        if len(self._buffer) > 0:

            #required = len(self._buffer) - self.fillLevel
            #time = required/fillRate
            # Round up to multiple of dripMinimum
            #time = math.ceil(time/self._dripMinimum) * self._dripMinimum

            #reactor.callLater(time, self._dripAndTryWrite)
   #         self.debug("Wrote all we could, fillLevel now %d, buffer not empty (%d", self.fillLevel, len(self._buffer))
            if not self._dripDC:
   #             self.debug("Writing more in %d s", self._dripMinimum)
                self._dripDC = reactor.callLater(self._dripMinimum, self._dripAndTryWrite)
   #         else:
   #             self.debug("drip already pending")
        elif self._finishing:
            self.consumer.finish()
        else:
        #    self.debug("No buffer left, asking %r to resume producing...", self.producer)
            if self.producer:
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
            #self.debug("Telling producer to produce more")
            self.producer.resumeProducing()

    def write(self, data):
        #self.debug("Received %d bytes, appending to buffer and trying to write", len(data))
        self._buffer += data

        self._tryWrite()

        if self._buffer and not self.fillLevel and self.producer:
            #self.debug("Have data but no bytes in bucket; pausing producing")
            self.producer.pauseProducing()

    def finish(self):
        self._finishing = True

    def registerProducer(self, producer, streaming):
        #self.debug("Producer %r registered", producer)
        self.producer = producer

        self.resumeProducing()

    def unregisterProducer(self):
        #self.debug("Producer %r unregistered", self.producer)
        if self.producer is not None:
            self.producer = None

            self.consumer.unregisterProducer()

