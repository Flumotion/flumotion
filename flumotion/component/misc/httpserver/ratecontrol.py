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

from flumotion.component.plugs import base as plugbase


class RateControllerPlug(plugbase.ComponentPlug):

    # Create a producer-consumer proxy that sits between a FileTransfer object
    # and a request object.
    # You may return a Deferred here.

    def createProducerConsumerProxy(self, consumer, request):
        pass


class RateControllerFixedPlug(RateControllerPlug):

    def __init__(self, args):
        props = args['properties']
        self._rateBytesPerSec = int(props.get('rate', 128000) / 8)
        # Peak level is 10 seconds of data; this is chosen
        # entirely arbitrarily.
        self._maxLevel = int(props.get('max-level',
            self._rateBytesPerSec * 8 * 10) / 8)
        self._initialLevel = int(props.get('initial-level', 0) / 8)

    def createProducerConsumerProxy(self, consumer, request):
        return TokenBucketConsumer(consumer, self._maxLevel,
            self._rateBytesPerSec, self._initialLevel)


class TokenBucketConsumer(log.Loggable):
    """
    Use a token bucket to proxy between a producer (e.g. FileTransfer) and a
    consumer (TCP protocol, etc.), doing rate control.

    The bucket has a rate and a maximum level, so a small burst can be
    permitted.  The initial level can be set to a non-zero value, this is
    useful to implement burst-on-connect behaviour.

    TODO: This almost certainly only works with producers that work like
    FileTransfer - i.e. they produce data directly in resumeProducing, and
    ignore pauseProducing. This is sufficient for our needs right now.
    """

    logCategory = 'token-bucket'

    # NOTE: Performance is strongly correlated with this value.
    # Low values (e.g. 0.2) give a 'smooth' transfer, but very high cpu usage
    # if you have several hundred clients.
    # Higher values (e.g. 1.0 or more) give bursty transfer, but nicely lower
    # cpu usage.
    _dripInterval = 1.0 # If we need to wait for more bits in our bucket, wait
                        # at least this long, to avoid overly frequent small
                        # writes

    def __init__(self, consumer, maxLevel, fillRate, fillLevel=0):
        self.maxLevel = maxLevel # in bytes
        self.fillRate = fillRate # in bytes per second
        self.fillLevel = fillLevel # in bytes

        self._buffers = [] # List of (offset, buffer) tuples
        self._buffersSize = 0

        self._finishing = False # If true, we'll stop once the current buffer
                                # has been sent.

        self._unregister = False # If true, we'll unregister from the consumer
                                 # once the data has been sent.

        self._lastDrip = time.time()
        self._dripDC = None
        self._paused = True

        self.producer = None # we get this in registerProducer.
        self.consumer = consumer

        # We are implemented as a push producer. We forcibly push some
        # data every couple of seconds to maintain the requested
        # rate. If the consumer cannot keep up with that rate we want
        # to get a pauseProducing() call, so we will stop
        # writing. Otherwise the data would have been buffered on the
        # server side, leading to excessive memory consumption.
        self.consumer.registerProducer(self, 1)

        self.info("Created TokenBucketConsumer with rate %d, "
                  "initial level %d, maximum level %d",
                  fillRate, fillLevel, maxLevel)

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
        if not self.consumer:
            return

        while self.fillLevel > 0 and self._buffersSize > 0:
            # If we're permitted to write at the moment, do so.
            offset, buf = self._buffers[0]
            sendbuf = buf[offset:offset+self.fillLevel]
            bytes = len(sendbuf)

            if bytes + offset == len(buf):
                self._buffers.pop(0)
            else:
                self._buffers[0] = (offset+bytes, buf)
            self._buffersSize -= bytes

            self.consumer.write(sendbuf)
            self.fillLevel -= bytes

        if self._buffersSize > 0:
            # If we have data (and we're not already waiting for our next drip
            # interval), wait... this is what actually performs the data
            # throttling.
            if not (self._dripDC or self._paused):
                self._dripDC = reactor.callLater(self._dripInterval,
                    self._dripAndTryWrite)
        else:
            # No buffer remaining; ask for more data or finish
            if self._finishing:
                if self._unregister:
                    self._doUnregister()
                self._doFinish()
            elif self.producer:
                self.producer.resumeProducing()
            elif self._unregister:
                self._doUnregister()

    def _doUnregister(self):
        self.consumer.unregisterProducer()
        self._unregister = False

    def _doFinish(self):
        self.debug('consumer <- finish()')
        self.consumer.finish()
        self._finishing = False

    def stopProducing(self):
        self.debug('stopProducing; buffered data: %d', self._buffersSize)
        if self.producer is not None:
            self.producer.stopProducing()

        if self._dripDC:
            # don't produce after stopProducing()!
            self._dripDC.cancel()
            self._dripDC = None

            # ...and then, we still may have pending things to do
            if self._unregister:
                self._doUnregister()

            if self._finishing:
                self._finishing = False
                self.consumer.finish()

        if self._buffersSize > 0:
            # make sure we release all the buffers, just in case
            self._buffers = []
            self._buffersSize = 0

        self.consumer = None

    def pauseProducing(self):
        self._paused = True

        # In case our producer is also 'push', we want it to stop.
        # FIXME: Pull producers don't even need to implement that
        # method, so we probably should remember what kind of producer
        # are we dealing with and not call pauseProducing when it's
        # 'pull'.
        # However, all our producers (e.g. FileProducer) just
        # ignore pauseProducing, so for now it works.
        self.producer.pauseProducing()

        # We have to stop dripping, otherwise we will keep on filling
        # the buffers and eventually run out of memory.
        if self._dripDC:
            self._dripDC.cancel()
            self._dripDC = None

    def resumeProducing(self):
        self._paused = False
        self._tryWrite()

        if not self._buffers and self.producer:
            self.producer.resumeProducing()

    def write(self, data):
        self._buffers.append((0, data))
        self._buffersSize += len(data)

        self._tryWrite()

        if self._buffers and not self.fillLevel and self.producer:
            # FIXME: That's not completely correct. See the comment in
            # self.pauseProducing() about not calling pauseProducing
            # on 'pull' producers.
            self.producer.pauseProducing()

    def finish(self):
        if self._dripDC:
            self._finishing = True
        elif self.consumer:
            self._doFinish()

    def registerProducer(self, producer, streaming):
        self.debug("Producer registered: %r", producer)
        self.producer = producer

        self.resumeProducing()

    def unregisterProducer(self):
        self.debug('unregisterProducer; buffered data: %d', self._buffersSize)
        if self.producer is not None:
            self.producer = None

            if not self._dripDC:
                self._doUnregister()
            else:
                # we need to wait until we've written the data
                self._unregister = True
