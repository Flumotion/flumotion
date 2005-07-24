# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005 Fluendo, S.L. (www.fluendo.com). All rights reserved.

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

class Colorbalance(feedcomponent.Effect):
    logCategory = "colorbalance"

    def __init__(self, name, element, hue, saturation, brightness, contrast):
        """
        @param element: the GStreamer element supporting the colorbalance
                        interface
        @param hue: the colorbalance hue, as a percentage
        @type  hue: float
        """
        feedcomponent.Effect.__init__(self, name)
        self._element = element
        element.connect('state-change', self._source_state_changed_cb,
            hue, saturation, brightness, contrast)
        self._channels = None
                                       
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
                device_value = _percent_to_value(value,
                    i.min_value, i.max_value)
                self.debug("setting percentage: %.1f, value %d <= %d <= %d" % (
                    value, i.min_value, device_value, i.max_value))
                self._element.set_value(i, device_value)
                device_value = self._element.get_value(i)
                self.debug("actually set: %.1f, value %d <= %d <= %d" % (
                    value, i.min_value, device_value, i.max_value))
                percent = _value_to_percent(device_value,
                    i.min_value, i.max_value)
                # notify all others too
                if not self.component:
                    self.warning("effect %s doesn't have a component" %
                        self.name)
                else:
                    self.component.adminCallRemote("effectPropertyChanged",
                        self.name, which, percent)
                return percent

        # didn't find it
        return value

    def effect_getColorBalanceProperties(self):
        """
        Returns: a list of (label, value) tuples.
        """
        retval = []
        if not self._channels:
            return retval
        for i in self._channels:
            self.debug('colorbalance %s: %d <= %d <= %d' % (
                i.label, i.min_value, self._element.get_value(i), i.max_value))
            percent_value = _value_to_percent(self._element.get_value(i),
                 i.min_value, i.max_value)
            self.debug('colorbalance value: %f' % percent_value)
            retval.append([i.label, percent_value])

        return retval

    # called to set initial properties based on state change
    def _source_state_changed_cb(self, element, old, new, 
                                 hue, saturation, brightness, contrast):
        if not (old == gst.STATE_READY and new == gst.STATE_PAUSED):
            return

        self.debug('source is PAUSED, setting initial color balance properties')
        self._channels = element.list_colorbalance_channels()
        self.debug('colorbalance channels: %d' % len(self._channels))
        if hue:
            self.effect_setColorBalanceProperty('Hue', hue)
        if saturation:
            self.effect_setColorBalanceProperty('Saturation', saturation)
        if brightness:
            self.effect_setColorBalanceProperty('Brightness', brightness)
        if contrast:
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
