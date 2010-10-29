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
import re

from twisted.python import failure
from twisted.internet import defer, reactor, interfaces, gtk2reactor
from twisted.web import client, error

from flumotion.common import testsuite, netutils
from flumotion.common import log, errors
from flumotion.common.planet import moods
from flumotion.component.consumers.httpstreamer import icystreamer, icymux
from flumotion.common import gstreamer

from flumotion.test import comptest

attr = testsuite.attr


class TestIcyStreamer(comptest.CompTestTestCase, log.Loggable):

    def setUp(self):
        self.tp = comptest.ComponentTestHelper()
        prod = ('audiotestsrc wave=silence ! ffenc_mp2 name=encoder')
        self.s =\
            'flumotion.component.consumers.httpserver.httpserver.ICYStreamer'

        self.prod = comptest.pipeline_src(prod)

    def tearDown(self):
        d = comptest.delayed_d(1, None)
        d.addCallback(comptest.cleanup_reactor)
        return d

    def _getFreePort(self):
        while True:
            port = netutils.tryPort()
            if port is not None:
                break

        return port

    def _initComp(self):
        self.compWrapper =\
           comptest.ComponentWrapper('icy-streamer', icystreamer.ICYStreamer,
                                     name='icy-streamer',
                                     props={'metadata-interval': 0.5,
                                            'port': self._getFreePort()})
        self.tp.set_flow([self.prod, self.compWrapper])


        d = self.tp.start_flow()
        d.addCallback(lambda _:
             self.__setattr__('comp', self.compWrapper.comp))
        # wait for the converter to go happy
        d.addCallback(lambda _: self.compWrapper.wait_for_mood(moods.happy))
        return d

    def _sendTitleEvent(self, title):
        struc = gst.Structure(name='taglist')
        struc.set_value('title', title.encode("utf-8", "replace"))
        self._sendEvent(struc)

    def _sendEvent(self, struc):
        encoder = self.prod.comp.pipeline.get_by_name('encoder')
        pad = encoder.get_pad('src')
        event = gst.event_new_custom(gst.EVENT_TAG, struc)
        res = pad.push_event(event)
        self.debug("Pushed event: %r with result: %r", event, res)

    def testInitialization(self):
        d = self._initComp()

        d.addCallback(lambda _: comptest.delayed_d(0.1, _))

        def _assertsOnSinks(_):
            # check if sinks and caps are initialized properly
            self.assertTrue(self.comp.hasCaps())
            capsExpected = {True: 'application/x-icy',
                            False: 'audio/mpeg'}
            for withID3 in capsExpected:
                # check caps
                sink = self.comp.sinksByID3[withID3]
                self.assertEqual(capsExpected[withID3],\
                    sink.caps[0].get_name())
                # check sync method (latest-keyframe)
                self.assertEqual(2, sink.get_property('sync-method'))
        d.addCallback(_assertsOnSinks)

        def assertBrSet(_):
            self.assertTrue('icy-br' in self.comp.icyHeaders)
        d.addCallback(assertBrSet)

        # and finally stop the flow
        d.addCallback(lambda _: self.tp.stop_flow())
        return d

    def testReceivingTagEvent(self):
        d = self._initComp()
        d.addCallback(lambda _: comptest.delayed_d(0.1, _))

        def assertTitleSet(title):
            self.assertEqual(title, \
                      self.comp.muxer.get_property('iradio-title'))

        # check if we respond currectly for title events
        d.addCallback(lambda _: self._sendTitleEvent('some title'))
        d.addCallback(lambda _: comptest.delayed_d(0.8, 'some title'))
        d.addCallback(assertTitleSet)

        d.addCallback(lambda _: self._sendTitleEvent('some other title'))
        d.addCallback(lambda _: comptest.delayed_d(0.8, 'some other title'))
        d.addCallback(assertTitleSet)

        # now check if the events setting response headers work
        mapping = {'icy-name': 'organization',
                   'icy-genre': 'genre',
                   'icy-url': 'location'}
        struc = gst.Structure(name='taglist')
        for key in mapping:
            struc.set_value(mapping[key], mapping[key])
        d.addCallback(lambda _: self._sendEvent(struc))

        def assertValuesInResponseHeadersSet(_):
            for key in mapping:
                self.assertTrue(key in self.comp.icyHeaders, key)
                self.assertEqual(mapping[key], self.comp.icyHeaders[key])
        d.addCallback(lambda _: comptest.delayed_d(0.5, _))
        d.addCallback(assertValuesInResponseHeadersSet)

        d.addCallback(lambda _: self.tp.stop_flow())
        return d

    def testStreamingICY(self):
        d = self._initComp()
        d.addCallback(lambda _: comptest.delayed_d(1, _))

        def getStream():
            icyMetaint = self.comp.muxer.get_property('icy-metaint')
            toDownload = 2 * icyMetaint + 200
            return downloadStream(self.comp.getUrl(),\
                           headers={'Icy-MetaData': 1}, limit=toDownload)

        def assertsOnStream(factory):
            icyMetaint = self.comp.muxer.get_property('icy-metaint')
            self.assertTrue('icy-metaint' in factory.response_headers)
            self.assertEqual(\
                str(icyMetaint), factory.response_headers['icy-metaint'][0])

            self.assertTrue('icy-br' in factory.response_headers)

            ct = factory.response_headers['content-type'][0]
            self.assertEqual('application/x-icy', ct)

            self.assertEqual(1, self.comp.getClients())


        d.addCallback(lambda _: getStream())
        d.addCallback(assertsOnStream)
        d.addCallback(lambda _: comptest.delayed_d(0.1, _))
        d.addCallback(lambda _: self.assertEqual(0, self.comp.getClients()))

        d.addCallback(lambda _: self.tp.stop_flow())
        return d

    def testStreamingNonICY(self):
        d = self._initComp()
        d.addCallback(lambda _: comptest.delayed_d(1, _))

        def getStream():
            icyMetaint = self.comp.muxer.get_property('icy-metaint')
            toDownload = 2 * icyMetaint + 200
            return downloadStream(self.comp.getUrl(), limit=toDownload)

        def assertsOnStream(factory):
            ct = factory.response_headers['content-type'][0]
            self.assertEqual('audio/mpeg', ct)

            self.assertEqual(1, self.comp.getClients())

        d.addCallback(lambda _: getStream())
        d.addCallback(assertsOnStream)
        d.addCallback(lambda _: comptest.delayed_d(0.1, _))
        d.addCallback(lambda _: self.assertEqual(0, self.comp.getClients()))

        d.addCallback(lambda _: self.tp.stop_flow())
        return d


def downloadStream(url, contextFactory=None, *args, **kwargs):
    scheme, host, port, path = client._parse(url)
    factory = StreamDownloader(url, *args, **kwargs)
    if scheme == 'https':
        from twisted.internet import ssl
        if contextFactory is None:
            contextFactory = ssl.ClientContextFactory()
        reactor.connectSSL(host, port, factory, contextFactory)
    else:
        reactor.connectTCP(host, port, factory)
    return factory.deferred


class StreamDownloader(client.HTTPDownloader):

    def __init__(self, url, **kwargs):
        if 'limit' in kwargs:
            self.limit = kwargs['limit']
            del(kwargs['limit'])
        else:
            raise ArgumentError("Limit keyword is required!")
        client.HTTPDownloader.__init__(self, url, None, **kwargs)
        self.requestedPartial = True
        self.buffer = ""

    def buildProtocol(self, addr):
        self.connector = client.HTTPDownloader.buildProtocol(self, addr)
        self.connector.quietLoss = True
        return self.connector

    def pagePart(self, data):
        self.buffer += data
        log.debug('stream-downloader', 'Got bytes %r, limit is %r' %\
                 (len(self.buffer), self.limit))
        if len(self.buffer) >= self.limit:
            self.finished = True
            log.debug('stream-downloader',\
                'Calling callback of StreamDownloader')
            self.deferred.addCallback(self.connector.transport.loseConnection)
            self.deferred.callback(self)

    def pageStart(self, partialContent):
        log.debug('stream-downloader', 'At pageStart... partialcontent=%r'%\
                partialContent)

    def openFile(self, partialContent):
        pass

    def gotHeaders(self, headers):
        self.response_headers = headers
