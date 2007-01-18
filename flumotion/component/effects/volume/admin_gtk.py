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

import gtk
import os
import math

from flumotion.common import errors, log

# import custom glade handler
from flumotion.ui import glade

from flumotion.component.base import admin_gtk

def clamp(x, min, max):
    if x < min:
        return min
    elif x > max:
        return max
    return x

class VolumeAdminGtkNode(admin_gtk.EffectAdminGtkNode):
    logCategory = 'volume'
    glade_file = os.path.join('flumotion', 'component', 'effects',
                              'volume', 'volume.glade')

    uiStateHandlers = None

    def haveWidgetTree(self):
        self.widget = self.wtree.get_widget('volume-widget')
        self.scale_volume = self.wtree.get_widget('level-widget')
        self._volume_set_label = self.wtree.get_widget('volume-set-label')
        self._volume_set_label.set_text('0')
        self.shown = False

        # now do the callbacks for the volume setting
        self._hscale = self.wtree.get_widget('volume-set-hscale')
        self._scale_changed_id = self._hscale.connect('value_changed',
                self.cb_volume_set)

        # callback for checkbutton
        check = self.wtree.get_widget('volume-set-check')
        check.connect('toggled', self._check_toggled_cb)

    def setUIState(self, state):
        admin_gtk.EffectAdminGtkNode.setUIState(self, state)
        if not self.uiStateHandlers:
            self.uiStateHandlers = {'volume-volume': self.volumeSet,
                                    'volume-peak': self.peakSet,
                                    'volume-decay': self.decaySet}
        for k, handler in self.uiStateHandlers.items():
            handler(state.get(k))

    def peakSet(self, peak):
        peak = sum(peak)/len(peak)
        self.scale_volume.set_property('peak', clamp(peak, -90.0, 0.0))

    def decaySet(self, decay):
        decay = sum(decay)/len(decay)
        self.scale_volume.set_property('decay', clamp(decay, -90.0, 0.0))

    # when volume has been set by another admin client
    def volumeSet(self, volume):
        self._hscale.handler_block(self._scale_changed_id)
        self._hscale.set_value(volume)
        dB = "- inf"
        if volume:
            dB = "%2.2f" % (20.0 * math.log10(volume))
        self._volume_set_label.set_text(dB)
        self._hscale.handler_unblock(self._scale_changed_id)

    def stateSet(self, state, key, value):
        handler = self.uiStateHandlers.get(key, None)
        if handler:
            handler(value)

    # run when the scale is moved by user
    def cb_volume_set(self, widget):
        # do something
        volume = self._hscale.get_value()
        #self.volumeSet(volume)
        d = self.effectCallRemote("setVolume", volume)
        d.addErrback(self.setVolumeErrback)

    def setVolumeErrback(self, failure):
        self.warning("Failure %s setting volume: %s" % (
            failure.type, failure.getErrorMessage()))
        return None

    def _update_volume_label(self):
        # update the volume label's dB value
        pass

    # when the "increase volume" checkbutton is toggled
    def _check_toggled_cb(self, widget):
        checked = widget.get_property('active')
        self.debug('checkbutton toggled; now %r' % checked)
        value = self._hscale.get_value()
        if checked:
            self._hscale.set_range(0.0, 4.0)
        else:
            if value > 1.0: value = 1.0
            self._hscale.set_range(0.0, 1.0)
        self.volumeSet(value)
            

