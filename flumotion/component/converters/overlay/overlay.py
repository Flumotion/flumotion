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

import gobject
import gst

from flumotion.common import messages, gstreamer
from flumotion.common.i18n import N_, gettexter
from flumotion.component import feedcomponent
from flumotion.component.converters.overlay import genimg

__version__ = "$Rev$"
T_ = gettexter()

# FIXME: This class only needed for gst-plugins-base < 0.10.22
# Remove when we do not need compatibility with < 0.10.22


class OverlayImageSource(gst.BaseSrc):
    __gstdetails__ = ('FluOverlaySrc', 'Source',
                      'Overlay Image source for flumotion', 'Zaheer Merali')
    __gsttemplates__ = (
        gst.PadTemplate("src",
                        gst.PAD_SRC,
                        gst.PAD_ALWAYS,
                        gst.caps_new_any()))
    imgBuf = ""
    capsStr = ""
    duration = 1.0/25

    def __init__(self):
        gst.BaseSrc.__init__(self)
        self.set_format(gst.FORMAT_TIME)

    def do_create(self, offset, length):
        self.debug("Pushing buffer")
        gstBuf = gst.Buffer(self.imgBuf)
        padcaps = gst.caps_from_string(self.capsStr)
        gstBuf.set_caps(padcaps)
        gstBuf.timestamp = 0
        gstBuf.duration = self.duration * gst.SECOND
        return gst.FLOW_OK, gstBuf


class Overlay(feedcomponent.ParseLaunchComponent):
    checkTimestamp = True
    checkOffset = True
    _filename = None
    CAPS_TEMPLATE = "video/x-raw-rgb,bpp=32,depth=32,width=%d,height=%d," \
            "red_mask=-16777216,green_mask=16711680,blue_mask=65280," \
            "alpha_mask=255,endianness=4321,framerate=0/1"

    def get_pipeline_string(self, properties):
        pipeline = ('@eater:default@ ! ffmpegcolorspace !'
            'video/x-raw-yuv,format=(fourcc)AYUV ! videomixer name=mix !'
            '@feeder:default@')
        return pipeline

    def _set_source_image(self, width, height):
        imgBuf, imagesOverflowed, textOverflowed = \
            genimg.generateOverlay(
                text=self.text,
                font=self.font,
                showFlumotion=self.showFlumotion,
                showCC=self.showCC,
                showXiph=self.showXiph,
                width=width, height=height)

        if textOverflowed:
            m = messages.Warning(
                T_(N_("Overlayed text '%s' too wide for the video image."),
                   self.text), mid="text-too-wide")
            self.addMessage(m)

        if imagesOverflowed:
            m = messages.Warning(
                T_(N_("Overlayed logotypes too wide for the video image.")),
                mid="image-too-wide")
            self.addMessage(m)

        if self.source.get_factory().get_name() == 'appsrc':
            self.imgBuf = imgBuf
        else:
            self.source.imgBuf = imgBuf

    def _set_source_caps(self, width, height):
        self.capsStr = self.CAPS_TEMPLATE % (width, height)
        if self.source.get_factory().get_name() == 'appsrc':
            self.source.set_property('caps', gst.Caps(self.capsStr))
        else:
            self.source.capsStr = self.capsStr

    def _set_source_framerate(self, framerate):
        self.duration = float(framerate.denom) / framerate.num
        if self.source.get_factory().get_name() != 'appsrc':
            self.source.duration = duration

    def _notify_caps_cb(self, pad, param):
        caps = pad.get_negotiated_caps()
        if caps is None:
            return
        struct = pad.get_negotiated_caps().get_structure(0)
        height = struct['height']
        width = struct['width']
        framerate = struct['framerate']

        self._set_source_image(width, height)
        self._set_source_caps(width, height)
        self._set_source_framerate(framerate)

        if not self.sourceBin.get_pad("src").is_linked():
            self.sourceBin.link_filtered(self.videomixer,
                gst.Caps("video/x-raw-yuv, format=(fourcc)AYUV"))
            self.sourceBin.set_locked_state(False)
            self.sourceBin.set_state(gst.STATE_PLAYING)

    def _add_source_bin(self, pipeline):
        if gstreamer.element_factory_exists("appsrc") and \
            gstreamer.get_plugin_version("app") >= (0, 10, 22, 0):
            self.source = gst.element_factory_make('appsrc', 'source')
            self.source.set_property('do-timestamp', True)
            self.source.connect('need-data', self.push_buffer)
        else:
            #FIXME: fluoverlaysrc only needed on gst-plugins-base < 0.10.22
            gobject.type_register(OverlayImageSource)
            gst.element_register(OverlayImageSource, "fluoverlaysrc",
                gst.RANK_MARGINAL)
            self.source = gst.element_factory_make('fluoverlaysrc', 'source')
        # create the source bin
        self.sourceBin = gst.Bin()
        # create the alphacolor element
        alphacolor = gst.element_factory_make('alphacolor')
        # add the elements to the source bin and link them
        self.sourceBin.add_many(self.source, alphacolor)
        self.source.link(alphacolor)
        pipeline.add(self.sourceBin)
        # create the source ghost pad
        self.sourceBin.add_pad(gst.GhostPad('src', alphacolor.get_pad('src')))
        # set the locked state and wait until we get the first caps change
        # and we know the widht and height of the input stream
        self.sourceBin.set_locked_state(True)

    def configure_pipeline(self, pipeline, properties):
        p = properties
        self.fixRenamedProperties(p, [
                ('show_text', 'show-text'),
                ('fluendo_logo', 'fluendo-logo'),
                ('cc_logo', 'cc-logo'),
                ('xiph_logo', 'xiph-logo')])

        if p.get('width', None) is not None:
            self.warnDeprecatedProperties(['width'])
        if p.get('height', None) is not None:
            self.warnDeprecatedProperties(['height'])

        self.font=p.get('font', None)
        self.showFlumotion=p.get('fluendo-logo', False)
        self.showCC=p.get('cc-logo', False)
        self.showXiph=p.get('xiph-logo', False)
        if p.get('show-text', False):
            self.text = p.get('text', 'set the "text" property')
        else:
            self.text = None

        vmixerVersion = gstreamer.get_plugin_version('videomixer')
        if vmixerVersion == (0, 10, 7, 0):
            m = messages.Warning(
                T_(N_("The 'videomixer' GStreamer element has a bug in this "
                      "version (0.10.7). You may see many errors in the debug "
                      "output, but it should work correctly anyway.")),
                mid="videomixer-bug")
            self.addMessage(m)

        self.videomixer = pipeline.get_by_name("mix")
        # add a callback for caps change to configure the image source
        # properly using the caps of the input stream
        self.videomixer.get_pad('sink_0').connect('notify::caps',
            self._notify_caps_cb)
        # the source is added to the pipeline, but it's not linked yet, and
        # remains with a locked state until we have enough info about the
        # input stream
        self._add_source_bin(pipeline)

    def push_buffer(self, source, arg0):
        """
        Pushes buffer to appsrc in GStreamer

        @param source: the appsrc element to push to
        @type source: GstElement
        """
        self.log("Pushing buffer")
        gstBuf = gst.Buffer(self.imgBuf)
        padcaps = gst.caps_from_string(self.capsStr)
        gstBuf.set_caps(padcaps)
        gstBuf.duration = int(self.duration * gst.SECOND)
        source.emit('push-buffer', gstBuf)
