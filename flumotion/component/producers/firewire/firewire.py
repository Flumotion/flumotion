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

from flumotion.common import messages, gstreamer
from flumotion.common.i18n import N_, gettexter
from flumotion.component.common.avproducer import avproducer

__version__ = "$Rev$"
T_ = gettexter()


# See comments in gstdvdec.c for details on the dv format.


class Firewire(avproducer.AVProducerBase):

    decoder = None
    decoder_str = 'dvdec'
    guid = 0

    def get_raw_video_element(self):
        return self.decoder

    def get_pipeline_template(self):
        # FIXME: might be nice to factor out dv1394src ! dvdec so we can
        # replace it with videotestsrc of the same size and PAR, so we can
        # unittest the pipeline
        # need a queue in case tcpserversink blocks somehow
        return ('dv1394src %s'
                '    ! tee name=t'
                '    ! queue leaky=2 max-size-time=1000000000'
                '    ! dvdemux name=demux'
                '  demux. ! queue ! %s name=decoder'
                '    ! @feeder:video@'
                '  demux. ! queue ! audio/x-raw-int '
                '    ! volume name=setvolume'
                '    ! level name=volumelevel message=true '
                '    ! @feeder:audio@'
                '    t. ! queue ! @feeder:dv@' % (self.guid, self.decoder_str))

    def configure_pipeline(self, pipeline, properties):
        # catch bus message for when camera disappears
        bus = pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message::element', self._bus_message_received_cb)

        self.decoder = pipeline.get_by_name("decoder")
        if gstreamer.element_has_property(self.decoder, 'drop-factor'):
            if self.framerate:
                framerate = float(self.framerate.num / self.framerate.denom)
                if 12.5 < framerate:
                    drop_factor = 1
                elif 6.3 < framerate <= 12.5:
                    drop_factor = 2
                elif 3.2 < framerate <= 6.3:
                    drop_factor = 4
                elif framerate <= 3.2:
                    drop_factor = 8
            else:
                drop_factor = 1
            self.decoder.set_property('drop-factor', drop_factor)
        return avproducer.AVProducerBase.configure_pipeline(self, pipeline,
                                                            properties)

    def _parse_aditional_properties(self, props):
        self.decoder_str = props.get('decoder', 'dvdec')
        self.guid = "guid=%s" % props.get('guid', 0)

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
            if 'current-device-change' in s.keys():
                if s['current-device-change'] != 0:
                    # we actually have a connect or disconnect of the camera
                    # so first remove all the previous messages warning about a
                    # firewire-bus-reset

                    for m in self.state.get('messages'):
                        if m.id.startswith('firewire-bus-reset'):
                            self.state.remove('messages', m)

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
