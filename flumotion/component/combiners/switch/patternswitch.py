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

from flumotion.common import errors, messages
from flumotion.common.i18n import N_, gettexter
from flumotion.component import feedcomponent
from flumotion.component.combiners.switch import basicwatchdog

__version__ = "$Rev$"
T_ = gettexter()


class PatternEventSwitcher(basicwatchdog.AVBasicWatchdog):
    logCategory = "comb-av-pattern-switcher"

    def do_check(self):
        d = basicwatchdog.AVBasicWatchdog.do_check(self)

        def checkConfig(result):
            props = self.config['properties']
            eaterName = props.get('eater-with-stream-markers', None)
            if eaterName != 'video-master' and eaterName != 'video-backup':
                warnStr = N_("The value provided for the " \
                    "eater-with-stream-markers property " \
                    "must be one of video-backup, video-master.")
                self.warning(warnStr)
                self.addMessage(messages.Error(T_(N_(warnStr)),
                    mid="eater-with-stream-markers-wrong"))
            return result
        d.addCallback(checkConfig)
        return d

    def configure_pipeline(self, pipeline, properties):
        basicwatchdog.AVBasicWatchdog.configure_pipeline(self, pipeline,
            properties)
        # set event probe to react to video mark events
        eaterName = properties.get('eater-with-stream-markers',
            'video-backup')
        sinkpad = self.videoSwitchElement.get_pad(self.switchPads[eaterName])
        sinkpad.add_event_probe(self._markers_event_probe)

    def _markers_event_probe(self, element, event):
        if event.type == gst.EVENT_CUSTOM_DOWNSTREAM:
            evt_struct = event.get_structure()
            if evt_struct.get_name() == 'FluStreamMark':
                if evt_struct['action'] == 'start':
                    self.switch_to("backup")

                elif evt_struct['action'] == 'stop':
                    self.switch_to("master")
        return True
