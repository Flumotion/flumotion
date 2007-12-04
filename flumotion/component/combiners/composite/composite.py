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

__version__ = "$Rev$"

from flumotion.component import feedcomponent

class Composite(feedcomponent.MultiInputParseLaunchComponent):
    logCategory = 'comb-composite'

    def init(self):
        self._pad_names = {}
        self._stream_props = {}

    def _parse_stream_props(self, properties):
        props = self._stream_props
        config = properties.get('input', [])

        for fp in config:
            fname = fp['feeder-alias']
            props[fname] = dict(xpos=fp.get('position-left', 0),
                                ypos=fp.get('position-top', 0),
                                zorder=fp.get('z-order', None),
                                alpha=fp.get('alpha', 1.0))

    def get_pipeline_string(self, properties):
        self._parse_stream_props(properties)

        # naming ffmpegcsp elements so we can easier identify mixer pads
        etmpl = '@ eater:%s @ ! ffmpegcolorspace name=csc-%s ! mixer. '
        pipeline = ('videomixer name=mixer %s mixer.' %
                    ' '.join([etmpl % (a, a) for a in self.eaters]))
        return pipeline

    def configure_pipeline(self, pipeline, properties):
        mixer = pipeline.get_by_name('mixer')

        for p in mixer.sink_pads():
            # get the coresponding ffmpegcsp's name and strip the
            # 'csc-' prefix
            peername = p.get_peer().get_parent().get_name()[4:]
            if peername in self.eaters:
                self._pad_names[peername] = p.get_name()

            cfg = self._stream_props.get(peername, None)
            if cfg:
                for k, v in cfg.items():
                    if v is not None:
                        p.set_property(k, v)
