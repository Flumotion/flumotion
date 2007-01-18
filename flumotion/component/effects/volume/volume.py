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

from math import frexp
from flumotion.component import feedcomponent

# FIXME: it's illogical to have to provide level, but not volume.

class Volume(feedcomponent.Effect):
    """
    I am an effect that can be added to any component that has a level
    element and a volume element.

    My component should implement setVolume() and getVolume()
    """
    logCategory = "volume"

    def __init__(self, name, element, pipeline):
        """
        @param element: the level element
        @param pipeline: the pipeline
        """
        feedcomponent.Effect.__init__(self, name)
        self._element = element
        # FIXME: set notification to every 1/5th sec, but maybe make
        # configurable ?
        element.set_property('interval', 200000000)
        bus = pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect('message::element', self._bus_message_received_cb)

    def setUIState(self, state):
        feedcomponent.Effect.setUIState(self, state)
        if state:
            for k in 'peak', 'decay', 'rms':
                state.addKey('volume-%s' % k, -100.0)
            state.addKey('volume-volume', self.effect_getVolume())

    def _bus_message_received_cb(self, bus, message):
        """
        @param bus: the message bus sending the message
        @param message: the message received
        """
        if message.structure.get_name() == 'level':
            s = message.structure
            peak = list(s['peak'])
            decay = list(s['decay'])
            rms = list(s['rms'])
            for l in peak, decay, rms:
                for v in l:
                    try:
                        v = frexp(v)
                    except (SystemError, OverflowError, ValueError):
                        # something confused log10() on the C side, punt
                        v = -100.0
            if not self.uiState:
                self.warning("effect %s doesn't have a uiState" %
                             self.name)
            else:
                for k, v in ('peak', peak), ('decay', decay), ('rms', rms):
                    self.uiState.set('volume-%s' % k, v)
            

    def effect_setVolume(self, value):
        """
        Sets volume

        @param value: what value to set volume to (float between 0.0 and 4.0)

        Returns: the actual value it was set to
        """
        self.component.setVolume(value)
        # notify admin clients
        self.uiState.set('volume-volume', value)

        return value

    def effect_getVolume(self):
        """
        Gets current volume setting.

        @return: what value the volume is set to
        @rtype:  float (between 0.0 and 4.0)
        """
        return self.component.getVolume()
