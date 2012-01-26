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

import gst
import urlparse

from twisted.internet import reactor

from flumotion.common import gstreamer
from flumotion.common.i18n import gettexter
from flumotion.component.base import http
from flumotion.component.component import moods
from flumotion.component.common.streamer.fragmentedstreamer import\
        FragmentedStreamer, Stats
from flumotion.component.consumers.hlsstreamer.resources import \
        HTTPLiveStreamingResource
from flumotion.component.consumers.hlsstreamer.hlsring import HLSRing
from flumotion.component.consumers.hlsstreamer import hlssink

__all__ = ['HLSStreamer']
__version__ = ""
T_ = gettexter()


SUPPORTED_FORMATS = {"video/mpegts": ("video/mpegts", "video/mpegts", "ts"),
                     "video/webm": ("video/webm", "video/webm", "webm")}


class HLSStreamer(FragmentedStreamer, Stats):
    DEFAULT_SESSION_TIMEOUT = 30
    DEFAULT_FRAGMENT_PREFIX = 'fragment'
    DEFAULT_MAIN_PLAYLIST = 'main.m3u8'
    DEFAULT_STREAM_PLAYLIST = 'stream.m3u8'
    DEFAULT_STREAM_BITRATE = 300000
    DEFAULT_KEYFRAMES_PER_SEGMENT = 10

    logCategory = 'hls-streamer'

    _mime_type = None
    _content_type = None
    _stream_setup = False

    def init(self):
        self.debug("HTTP live streamer initialising")
        self.hlsring = None

    def get_mime(self):
        return self._mime_type

    def get_content_type(self):
        return self._content_type

    def get_pipeline_string(self, properties):
        # Always use the python element for now. The C element will be used
        # when it is mature enough.
        # if not gstreamer.element_factory_exists('hlssink'):
        hlssink.register()
        return "hlssink name=sink sync=false"

    def configure_auth_and_resource(self):
        self.httpauth = http.HTTPAuthentication(self)
        self.resource = HTTPLiveStreamingResource(self, self.httpauth,
                self.secret_key, self.session_timeout)

    def getRing(self):
        return self.hlsring

    def configure_pipeline(self, pipeline, props):
        self.hlsring = HLSRing(
            props.get('main-playlist', self.DEFAULT_MAIN_PLAYLIST),
            props.get('stream-playlist', self.DEFAULT_STREAM_PLAYLIST),
            props.get('stream-bitrate', self.DEFAULT_STREAM_BITRATE),
            self.description,
            props.get('fragment-prefix', self.DEFAULT_FRAGMENT_PREFIX),
            props.get('new-fragment-tolerance', 0),
            props.get('max-window', self.DEFAULT_MAX_WINDOW),
            props.get('max-extra-buffers', None),
            props.get('key-rotation', 0),
            props.get('keys-uri', None))

        # Call the base class after initializing the ring and getting
        # the secret key and the session timeout
        FragmentedStreamer.configure_pipeline(self, pipeline, props)

        self.hls_url = props.get('hls-url', None)
        if self.hls_url:
            if not self.hls_url.endswith('/'):
                self.hls_url += '/'
            if self.mountPoint.startswith('/'):
                mp = self.mountPoint[1:]
            else:
                mp = self.mountPoint
            self.hls_url = urlparse.urljoin(self.hls_url, mp)
        else:
            self.hls_url = self.getUrl()

        self.hlsring.setHostname(self.hls_url)
        self.soft_restart()

    def soft_restart(self):
        """Stops serving fragments, resets the playlist and starts
        waiting for new segments to become happy again
        """
        self.info("Soft restart, resetting playlist and waiting to fill "
                  "the initial fragments window")
        self._ready = False
        self._fragmentsCount = 0
        self._last_index = 0
        self.hlsring.reset()

    def _setup_stream_type(self, stream_type):
        self.info("Setting up streamer for stream type %s", stream_type)
        mime_type, content_type, frag_ext = SUPPORTED_FORMATS[stream_type]
        self._mime_type = mime_type
        self._content_type = content_type
        self.hlsring.filenameExt = frag_ext
        self._stream_setup = True

    def _configure_sink(self):
        self.sink.set_property('write-to-disk', False)
        self.sink.set_property('playlist-max-window', 5)

    def _connect_sink_signals(self):
        FragmentedStreamer._connect_sink_signals(self)
        self.sink.connect("new-fragment", self._new_fragment)

    def _process_fragment(self, fragment):

        if not self._stream_setup:
            sink = self.get_element("sink")
            pad = sink.get_pad("sink")
            caps = pad.get_negotiated_caps()
            name = caps.get_structure(0).get_name()
            self._setup_stream_type(name)

        self._fragmentsCount = self._fragmentsCount + 1

        # Wait hls-min-window fragments to set the component 'happy'
        if self._fragmentsCount == self._minWindow:
            self.info("%d fragments received. Changing mood to 'happy'",
                    self._fragmentsCount)
            self.setMood(moods.happy)
            self._ready = True

        b = fragment.get_property('buffer')
        index = fragment.get_property('index')
        duration = fragment.get_property('duration')

        if index < self._last_index:
            self.warning("Found a discontinuity last index is %s but current "
                         "one is %s", self._last_index, index)
            self.soft_restart()

        fragName = self.hlsring.addFragment(b.data, index,
                round(duration / float(gst.SECOND)))
        self.info('Added fragment "%s", index=%s, duration=%s',
                  fragName, index, gst.TIME_ARGS(duration))

    ### START OF THREAD-AWARE CODE (called from non-reactor threads)

    def _new_fragment(self, hlssink):
        self.log("hlsink created a new fragment")
        try:
            fragment = hlssink.get_property('fragment')
        except:
            fragment = hlssink.emit('pull-fragment')
        reactor.callFromThread(self._process_fragment, fragment)

    ### END OF THREAD-AWARE CODE
