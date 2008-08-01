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
import gst.interfaces

from flumotion.component import feedcomponent

__version__ = "$Rev$"


class Colorbalance(feedcomponent.Effect):
    logCategory = "colorbalance"

    def __init__(self, name, element, hue, saturation, brightness, contrast,
        pipeline=None):
        """
        @param element: the GStreamer element supporting the colorbalance
                        interface
        @param hue: the colorbalance hue, as a percentage
        @type  hue: float
        @param saturation: the colorbalance saturation, as a percentage
        @type saturation: float
        @param brightness: the colorbalance brightness, as a percentage
        @type brightness: float
        @param contrast: the colorbalance contrast, as a percentage
        @type contrast: float
        @param pipeline: the pipeline
        @type pipeline: L{gst.Pipeline}
        """
        self.debug("colorbalance init")
        feedcomponent.Effect.__init__(self, name)
        self._element = element
        if pipeline:
            bus = pipeline.get_bus()
            bus.connect('message::state-changed',
                self._bus_message_received_cb,
                hue, saturation, brightness, contrast)

        self._channels = None

    def setUIState(self, state):
        feedcomponent.Effect.setUIState(self, state)
        if state:
            for k in 'Hue', 'Saturation', 'Brightness', 'Contrast':
                state.addKey('colorbalance-%s' % k, 0.0)

    # State change handling for 0.10

    def _bus_message_received_cb(self, bus, message, hue, saturation,
        brightness, contrast):
        """
        @param bus: the message bus sending the message
        @param message: the message received
        """
        t = message.type
        if t == gst.MESSAGE_STATE_CHANGED and message.src == self._element:
            (old, new, pending) = message.parse_state_changed()
            # we have a state change
            if old == gst.STATE_READY and new == gst.STATE_PAUSED:
                self._setInitialColorBalance(hue,
                    saturation, brightness, contrast)

    def effect_setColorBalanceProperty(self, which, value):
        """
        Set a color balance property.

        @param which: which property to change
        @param value: what value to set it to (float between 0.0 and 100.0)

        Returns: the actual percentage it was set to
        """
        if not self._channels:
            return value

        for i in self._channels:
            if i.label == which:
                if value:
                    device_value = _percent_to_value(value,
                        i.min_value, i.max_value)
                    self.debug("setting percentage: %.1f, "
                               "value %d <= %d <= %d",
                               value, i.min_value, device_value,
                               i.max_value)
                    self._element.set_value(i, device_value)
                device_value = self._element.get_value(i)
                percent = _value_to_percent(device_value,
                    i.min_value, i.max_value)
                self.debug('device says %s=%.1f', i.label, percent)
                # notify all others too
                if not self.uiState:
                    self.warning("effect %s doesn't have a uiState" %
                        self.name)
                else:
                    self.uiState.set('colorbalance-%s' % which, percent)
                return percent

        # didn't find it
        return value

    def _setInitialColorBalance(self, hue, saturation, brightness, contrast):
        self._channels = self._element.list_colorbalance_channels()
        self.debug('colorbalance channels: %d' % len(self._channels))
        self.effect_setColorBalanceProperty('Hue', hue)
        self.effect_setColorBalanceProperty('Saturation', saturation)
        self.effect_setColorBalanceProperty('Brightness', brightness)
        self.effect_setColorBalanceProperty('Contrast', contrast)


def _value_to_percent(value, min, max):
    """
    Convert an integer value between min and max to a percentage.
    """
    return float(value - min) / float(max - min) * 100.0


def _percent_to_value(percentage, min, max):
    """
    Convert an percentage value to an integer value between min and max.
    """
    return int(min + percentage / 100.0 * (max - min))
