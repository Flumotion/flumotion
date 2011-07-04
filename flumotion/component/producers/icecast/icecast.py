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
from twisted.internet import defer, reactor
from flumotion.component import feedcomponent
from flumotion.twisted.defer import RetryingDeferred
from flumotion.common import errors

__version__ = "$Rev$"


class Icecast(feedcomponent.ParseLaunchComponent):

    def get_pipeline_string(self, properties):
        return "souphttpsrc name=src ! typefind name=tf"

    def _typefind_have_caps_cb(self, tf, prob, caps):
        # Basing on the cappabilities plug additional gst compoponents:
        # 1. If we have pure audio (http src doesn't support ICY) plug parser
        # 2. If we have application/x-icy plug the icydemuxer and than parser
        capsname = caps[0].get_name()
        tf_src_pad = tf.get_pad('src')
        gdp_sink_pad = tf_src_pad.get_peer()
        # unlink the typefind from the gdp pad so that we can put another
        # component in it's place
        tf_src_pad.unlink(gdp_sink_pad)

        if capsname == 'application/x-icy':
            demuxer = gst.element_factory_make("icydemux")
            demuxer.set_state(gst.STATE_PLAYING)
            self.pipeline.add(demuxer)
            tf.link(demuxer)
            # demuxer src pad is dynamic, we need to register a callback
            demuxer.connect('pad-added', self._link_parser, gdp_sink_pad)
        else:
            self._link_parser(tf, tf_src_pad, gdp_sink_pad)

    def _link_parser(self, element, pad, gdp_sink_pad):
        # Append the audio parser to the end of the pipeline
        caps = pad.get_caps()
        capsname = caps.get_structure(0).get_name()
        parser = None
        if self.passthrough:
            self.info("Acting in passthrough mode, not parsing the audio")
            pad.link(gdp_sink_pad)
            return
        if capsname == 'application/ogg':
            parser = gst.element_factory_make('oggparse')
        elif capsname == 'audio/mpeg':
            parser = gst.element_factory_make('mp3parse')

        if parser:
            parser.set_state(gst.STATE_PLAYING)
            self.pipeline.add(parser)
            element.link(parser)
            parser.get_pad('src').link(gdp_sink_pad)
        else:
            # in case we good sth else than mp3 or ogg just connect the
            # gdb back
            self.warning("Couldn't find the correct parser for caps: %s",\
                capsname)
            pad.link(gdp_sink_pad)

    def configure_pipeline(self, pipeline, properties):
        # Later, when the typefind element has successfully found the type
        # of the data, we'll rebuild the pipeline.
        self.src = pipeline.get_by_name('src')
        self.url = properties['url']
        self.passthrough = properties.get('passthrough', False)
        self.src.set_property('location', self.url)
        self.src.set_property('iradio-mode', True)

        typefind = pipeline.get_by_name('tf')
        self.signal_id = typefind.connect('have-type',\
                self._typefind_have_caps_cb)

        self._pad_monitors.attach(self.src.get_pad('src'), 'souphttp-src')
        self._pad_monitors['souphttp-src'].addWatch(
                self._src_connected, self._src_disconnected)
        self.reconnecting = False
        self.reconnector = RetryingDeferred(self.connect)
        self.reconnector.initialDelay = 1.0
        self.attemptD = None

        def _drop_eos(pad, event):
            self.debug('Swallowing event %r', event)
            if event.type == gst.EVENT_EOS:
                return False
            return True
        self.src.get_pad('src').add_event_probe(_drop_eos)

    def bus_message_received_cb(self, bus, message):
        if message.type == gst.MESSAGE_ERROR and message.src == self.src:
            gerror, debug = message.parse_error()
            self.warning('element %s error %s %s',
                    message.src.get_path_string(), gerror, debug)
            if self.reconnecting:
                self._retry()
            return True
        feedcomponent.ParseLaunchComponent.bus_message_received_cb(
                self, bus, message)

    def connect(self):
        self.info('Connecting to icecast server on %s', self.url)
        self.src.set_state(gst.STATE_READY)
        # can't just self.src.set_state(gst.STATE_PLAYING),
        # because the pipeline might NOT be in PLAYING,
        # if we never connected to Icecast and never went to PLAYING
        self.try_start_pipeline(force=True)
        self.attemptD = defer.Deferred()
        return self.attemptD

    def _src_connected(self, name):
        self.info('Connected to icecast server on %s', self.url)
        if self.reconnecting:
            assert self.attemptD
            self.attemptD.callback(None)
            self.reconnecting = False

    def _src_disconnected(self, name):
        self.info('Disconnected from icecast server on %s', self.url)
        if not self.reconnecting:
            self.reconnecting = True
            self.reconnector.start()

    def _retry(self):
        assert self.attemptD
        self.debug('Retrying connection to icecast server on %s', self.url)
        self.attemptD.errback(errors.ConnectionError)
