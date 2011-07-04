# -*- Mode: Python; test-case-name: flumotion.test.test_http -*-
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

import time

import gst
from twisted.internet import reactor, defer
from zope.interface import implements

from flumotion.common import interfaces
from flumotion.component.base import http
from flumotion.component.consumers.httpstreamer import resources

from httpstreamer import MultifdSinkStreamer, Stats

# this import registers the gstreamer icymux element, don't remove it
import icymux


__all__ = ['ICYStreamer']
__version__ = "$Rev$"


class ICYStreamer(MultifdSinkStreamer):
    implements(interfaces.IStreamingComponent)

    checkOffset = True

    logCategory = 'icy-http'

    pipe_template = 'identity name=input silent=true ! tee name=tee ' +  \
        'tee. ! queue ! multifdsink name=sink-without-id3 sync=false ' + \
        'recover-policy=3 ' + \
        'tee. ! queue ! icymux name=mux ! ' + \
        'multifdsink name=sink-with-id3 sync=false recover-policy=3'

    defaultSyncMethod = 2
    defaultFrameSize = 256
    defaultMetadataInterval = 2

    def init(self):
        MultifdSinkStreamer.init(self)

        # fd -> sink
        self.sinkConnections = {}
        # headers to be included in HTTP response
        self.icyHeaders = {}

        for i in ('icy-title', 'icy-timestamp'):
            self.uiState.addKey(i, None)

        # fired after we receive first datablock and configure muxer
        self._muxerConfiguredDeferred = defer.Deferred()

    def configureAuthAndResource(self):
        self.httpauth = http.HTTPAuthentication(self)
        self.resource = resources.ICYStreamingResource(self,
                                                        self.httpauth)

    def configure_pipeline(self, pipeline, properties):
        self.sinksByID3 =\
                {False: self.get_element('sink-without-id3'),
                 True: self.get_element('sink-with-id3')}
        Stats.__init__(self, self.sinksByID3.values())

        self._updateCallLaterId = reactor.callLater(10, self._updateStats)

        self.configureAuthAndResource()
        self.parseProperties(properties)

        for sink in self.sinks:
            self.configureSink(sink)

        pad = pipeline.get_by_name('tee').get_pad('sink')
        pad.add_event_probe(self._tag_event_cb)

        self.configureMuxer(pipeline)

    def _tag_event_cb(self, pad, event):

        def store_tag(struc, headerKey, structureKey):
            if structureKey in struc.keys():
                self.icyHeaders[headerKey] = struc[structureKey]
                self.debug("Set header key %s = %s", \
                        headerKey, struc[structureKey])

        mapping = {'icy-name': 'organization',
                   'icy-genre': 'genre',
                   'icy-url': 'location'}
        if event.type == gst.EVENT_TAG:
            struc = event.get_structure()
            self.debug('Structure keys of tag event: %r', struc.keys())
            for headerName in mapping:
                reactor.callFromThread(\
                        store_tag, struc, headerName, mapping[headerName])
        return True

    def parseProperties(self, properties):
        MultifdSinkStreamer.parseProperties(self, properties)

        self._frameSize = properties.get('frame-size', self.defaultFrameSize)
        self._metadataInterval = properties.get('metadata-interval', \
                                                 self.defaultMetadataInterval)

    def configureMuxer(self, pipeline):
        self.muxer = pipeline.get_by_name('mux')
        self.muxer.set_property('frame-size', self._frameSize)

        def _setMuxerBitrate(bitrate):
            numFrames = int(self._metadataInterval * bitrate / \
                            8 / self._frameSize)
            self.debug("Setting number of frames to %r", numFrames)
            self.muxer.set_property('num-frames', numFrames)

            self.icyHeaders['icy-br'] = bitrate / 1000
            self.icyHeaders['icy-metaint'] = \
                self.muxer.get_property("icy-metaint")
            self._muxerConfiguredDeferred.callback(None)

        def _calculateBitrate(pad, data):
            self.debug('Calculating bitrate of the stream')
            bitrate = 8 * data.size * gst.SECOND / data.duration
            self.debug('bitrate: %r', bitrate)
            pad.remove_event_probe(handler_id)
            reactor.callFromThread(_setMuxerBitrate, bitrate)
        handler_id = self.pipeline.get_by_name('input').get_pad('sink').\
                                add_buffer_probe(_calculateBitrate)

    def get_content_type(self):
        # The content type should always be the content type of the stream as
        # some players do not understand "application/x-icy"
        sink = self.sinksByID3[False]
        if sink.caps:
            self.debug('Caps: %r', sink.caps.to_string())
            cap = sink.caps[0]
            if cap.get_name() == 'audio/mpeg':
                if cap['mpegversion']==2:
                    return 'audio/aacp'
            return cap.get_name()

    def add_client(self, fd, request):
        sink = self.sinksByID3[request.serveIcy]
        self.debug("Adding client to sink: %r", sink)
        self.sinkConnections[fd] = sink

        if request.serveIcy:
            # FIXME: This sends title to every connected client.
            # We should sent it only to the newly comming in client, but this
            # requires patching multifdsink
            self.muxer.emit('broadcast-title')
        sink.emit('add', fd)

    def remove_client(self, fd):
        sink = self.sinkConnections[fd]
        sink.emit('remove', fd)
        del self.sinkConnections[fd]

    def get_icy_headers(self):
        self.debug("Icy headers: %r", self.icyHeaders)
        return self.icyHeaders

    def updateState(self, set):
        Stats.updateState(self, set)

        set('icy-title', self.muxer.get_property('iradio-title'))
        timestamp = time.strftime("%c", time.localtime(\
                self.muxer.get_property('iradio-timestamp')))
        set('icy-timestamp', timestamp)

    def do_pipeline_playing(self):
        # change the component mood to happy after we receive first data block
        # so that we can calculate the bitrate and configure muxer
        d = MultifdSinkStreamer.do_pipeline_playing(self)
        return defer.DeferredList([d, self._muxerConfiguredDeferred])
