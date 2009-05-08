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

    def __init__(self):
        gst.BaseSrc.__init__(self)
        self.set_format(gst.FORMAT_TIME)

    def do_create(self, offset, length):
        self.debug("Pushing buffer")
        gstBuf = gst.Buffer(self.imgBuf)
        padcaps = gst.caps_from_string(self.capsStr)
        gstBuf.set_caps(padcaps)
        gstBuf.timestamp = 0
        gstBuf.duration = pow(2, 63) -1
        return gst.FLOW_OK, gstBuf


class Overlay(feedcomponent.ParseLaunchComponent):
    checkTimestamp = True
    checkOffset = True
    _filename = None

    def get_pipeline_string(self, properties):
        # the order here is important; to have our eater be the reference
        # stream for videomixer it needs to be specified last
        source_element = ""
        if gstreamer.element_factory_exists("appsrc") and \
            gstreamer.get_plugin_version("app") >= (0, 10, 22, 0):
            source_element = "appsrc name=source do-timestamp=true"
        else:
            #FIXME: fluoverlaysrc only needed on gst-plugins-base < 0.10.22
            gobject.type_register(OverlayImageSource)
            ret = gst.element_register(OverlayImageSource, "fluoverlaysrc",
                gst.RANK_MARGINAL)
            source_element = "fluoverlaysrc name=source "
        pipeline = (
            '%s ! alphacolor ! '
            'videomixer name=mix ! @feeder:default@ '
            '@eater:default@ ! ffmpegcolorspace ! mix.' % source_element)

        return pipeline

    def configure_pipeline(self, pipeline, properties):
        p = properties
        self.fixRenamedProperties(p, [
                ('show_text', 'show-text'),
                ('fluendo_logo', 'fluendo-logo'),
                ('cc_logo', 'cc-logo'),
                ('xiph_logo', 'xiph-logo')])

        text = None
        if p.get('show-text', False):
            text = p.get('text', 'set the "text" property')
        self.imgBuf, imagesOverflowed, textOverflowed = \
            genimg.generateOverlay(
                text=text,
                showFlumotion=p.get('fluendo-logo', False),
                showCC=p.get('cc-logo', False),
                showXiph=p.get('xiph-logo', False),
                width=p['width'],
                height=p['height'])

        if textOverflowed:
            m = messages.Warning(
                T_(N_("Overlayed text '%s' too wide for the video image."),
                   text), mid="text-too-wide")
            self.addMessage(m)

        if imagesOverflowed:
            m = messages.Warning(
                T_(N_("Overlayed logotypes too wide for the video image.")),
                mid="image-too-wide")
            self.addMessage(m)
        self.capsStr = "video/x-raw-rgb,bpp=32,depth=32,width=%d,height=%d," \
            "red_mask=-16777216,green_mask=16711680,blue_mask=65280," \
            "alpha_mask=255,framerate=0/1" % (p['width'], p['height'])
        padcaps = gst.caps_from_string(self.capsStr)
        source = self.get_element('source')
        if source.get_factory().get_name() == 'appsrc':
            # push buffer when we need to, currently we push a duration of
            # G_MAXINT_64 so we never need to push another one
            # but if we want dynamic change of overlay, we should make
            # duration tunable in properties
            source.connect('need-data', self.push_buffer)
            source.props.caps = padcaps
        else:
            # FIXME: fluoverlaysrc only needed on gst-plugins-base < 0.10.22
            source.imgBuf = self.imgBuf
            source.capsStr = self.capsStr
        vmixerVersion = gstreamer.get_plugin_version('videomixer')
        if vmixerVersion == (0, 10, 7, 0):
            m = messages.Warning(
                T_(N_("The 'videomixer' GStreamer element has a bug in this "
                      "version (0.10.7). You may see many errors in the debug "
                      "output, but it should work correctly anyway.")),
                mid="videomixer-bug")
            self.addMessage(m)

    def push_buffer(self, source, arg0):
        """
        Pushes buffer to appsrc in GStreamer

        @param source: the appsrc element to push to
        @type source: GstElement
        """
        self.debug("Pushing buffer")
        gstBuf = gst.Buffer(self.imgBuf)
        padcaps = gst.caps_from_string(self.capsStr)
        gstBuf.set_caps(padcaps)
        gstBuf.duration = pow(2, 63) -1
        source.emit('push-buffer', gstBuf)
