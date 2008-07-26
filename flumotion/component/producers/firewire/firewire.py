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
from twisted.internet import defer

from flumotion.common import errors, messages
from flumotion.common.i18n import N_, gettexter
from flumotion.component import feedcomponent

__version__ = "$Rev$"
T_ = gettexter()


# See comments in gstdvdec.c for details on the dv format.

class Firewire(feedcomponent.ParseLaunchComponent):
    def do_check(self):
        self.debug('running PyGTK/PyGST checks')
        from flumotion.component.producers import checks
        d1 = checks.checkTicket347()
        d2 = checks.checkTicket348()
        dl = defer.DeferredList([d1, d2])
        dl.addCallback(self._checkCallback)
        return dl

    def _checkCallback(self, results):
        for (state, result) in results:
            for m in result.messages:
                self.addMessage(m)

    def get_pipeline_string(self, props):
        width = props.get('width', 240)
        height = props.get('height', int(576 * width/720.)) # assuming PAL :-/
        guid = props.get('guid', None)

        # F0.6: remove backwards-compatible properties
        self.fixRenamedProperties(props, [
            ('scaled_width', 'scaled-width'),
            ('is_square',    'is-square'),
            ])
        scaled_width = props.get('scaled-width', width)
        is_square = props.get('is-square',  False)
        framerate = props.get('framerate', (30, 2))
        framerate_float = float(framerate[0]) / framerate[1]

        scale_correction = width - scaled_width

        if 12.5 < framerate_float <= 25:
            drop_factor = 1
        elif 6.3 < framerate_float <= 12.5:
            drop_factor = 2
        elif 3.2 < framerate_float <= 6.3:
            drop_factor = 4
        else:
            drop_factor = 8

        if is_square:
            square_pipe = ',pixel-aspect-ratio=(fraction)1/1'
        else:
            square_pipe = ''

        # the point of width correction is to get to a multiple of 8 for width
        # so codecs are happy; it's unrelated to the aspect ratio correction
        # to get to 4:3 or 16:9
        if scale_correction > 0:
            # videobox in 0.8.8 has a stride problem outputting AYUV with odd
            # width I420 works fine, but is slower when overlay is used

            pad_pipe = '! ffmpegcolorspace ! videobox right=-%d ! video/x-raw-yuv,format=(fourcc)I420 ' % scale_correction
        else:
            pad_pipe = ''

        # Always scale down to half size to lose interlacing artifacts.
        # FIXME: handle this better when GStreamer provides facilities for it.
        interlaced_height = 288

        # FIXME: might be nice to factor out dv1394src ! dvdec so we can
        # replace it with videotestsrc of the same size and PAR, so we can
        # unittest the pipeline
        # need a queue in case tcpserversink blocks somehow
        template = ('dv1394src %(guid)s'
                    '    ! tee name=t'
                    '    ! queue leaky=2 max-size-time=1000000000'
                    '    ! dvdemux name=demux'
                    '  demux. ! queue ! dvdec drop-factor=%(df)d'
                    '    ! video/x-raw-yuv,format=(fourcc)YUY2'
                    '    ! videorate ! videoscale'
                    '    ! video/x-raw-yuv,width=%(sw)s,height=%(ih)s%(sq)s'
                    '    ! videoscale'
                    '    ! video/x-raw-yuv,width=%(sw)s,height=%(h)s,framerate=%(fr)s,format=(fourcc)YUY2'
                    '    %(pp)s'
                    '    ! @feeder:video@'
                    '  demux. ! queue ! audio/x-raw-int ! volume name=setvolume'
                    '    ! level name=volumelevel message=true ! audiorate'
                    '    ! @feeder:audio@'
                    '    t. ! queue ! @feeder:dv@'
                    % dict(df=drop_factor, ih=interlaced_height,
                           sq=square_pipe, pp=pad_pipe,
                           sw=scaled_width, h=height,
                           guid=(guid and ('guid=%s' % guid) or ''),
                           fr=('%d/%d' % (framerate[0], framerate[1]))))

        return template

    def configure_pipeline(self, pipeline, properties):
        self.volume = pipeline.get_by_name("setvolume")
        from flumotion.component.effects.volume import volume
        comp_level = pipeline.get_by_name('volumelevel')
        vol = volume.Volume('inputVolume', comp_level, pipeline)
        # catch bus message for when camera disappears
        bus = pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message::element', self._bus_message_received_cb)

        self.addEffect(vol)

    def getVolume(self):
        return self.volume.get_property('volume')

    def setVolume(self, value):
        """
        @param value: float between 0.0 and 4.0
        """
        self.debug("Setting volume to %f" % (value))
        self.volume.set_property('volume', value)

    # detect camera unplugging or other cause of firewire bus reset
    def _bus_message_received_cb(self, bus, message):
        """
        @param bus: the message bus sending the message
        @param message: the message received
        """
        if message.structure.get_name() == "ieee1394-bus-reset":
            # we have a firewire bus reset
            s = message.structure
            # current-device-change is only in gst-plugins-good >= 0.10.3
            if s.has_key('current-device-change'):
                if s['current-device-change'] != 0:
                    # we actually have a connect or disconnect of the camera
                    # so first remove all the previous messages warning about a
                    # firewire-bus-reset

                    for m in self.state.get('messages'):
                        if m.id.startswith('firewire-bus-reset'):
                            self.state.remove('messages',m)

                    if s['current-device-change'] == 1:
                        # connected
                        m = messages.Info(T_(N_(
                            "The camera has now been reconnected.")),
                            mid="firewire-bus-reset-%d" % s['nodecount'],
                            priority=40)
                        self.state.append('messages', m)
                    elif s['current-device-change'] == -1:
                        # disconnected
                        m = messages.Warning(T_(N_(
                            "The camera has been disconnected.")),
                            mid="firewire-bus-reset-%d" % s['nodecount'],
                            priority=40)
                        self.state.append('messages', m)
