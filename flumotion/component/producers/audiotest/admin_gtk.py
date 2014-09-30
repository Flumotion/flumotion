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

from gettext import gettext as _

from flumotion.component.base.admin_gtk import BaseAdminGtk
from flumotion.component.base.baseadminnode import BaseAdminGtkNode
from flumotion.component.effects.volume.admin_gtk import VolumeAdminGtkNode

__version__ = "$Rev$"


class AudioTestAdminGtkNode(BaseAdminGtkNode):
    logCategory = 'audiotest'
    gladeFile = 'flumotion/component/producers/audiotest/audiotest.glade'
    uiStateHandlers = None

    def haveWidgetTree(self):
        self.widget = self.wtree.get_widget('widget-audiotest')
        self._scale = self.wtree.get_widget('scale-frequency')
        self._spinbutton = self.wtree.get_widget('spinbutton-frequency')
        self._combobox = self.wtree.get_widget('combobox-wave')
        self._combobox.prefill(['Sine', 'Square', 'Saw', 'Triangle', 'Silence',
                                'White-noise', 'Pink-noise', 'Sine table',
                                'Ticks'])

        self._scale_change_id = self._scale.connect('value-changed',
            self.frequency_changed_cb)
        self._spinbutton_change_id = self._spinbutton.connect('value-changed',
            self.frequency_changed_cb)
        self._combobox_change_id = self._combobox.connect('changed',
            self.wave_changed_cb)

    def setUIState(self, state):
        BaseAdminGtkNode.setUIState(self, state)
        if not self.uiStateHandlers:
            self.uiStateHandlers = {'wave': self.waveSet,
                                    'frequency': self.frequencySet,
                                    'samplerate': self.samplerateSet}
        for k, handler in self.uiStateHandlers.items():
            handler(state.get(k))

    def frequency_changed_cb(self, widget):
        value = widget.get_value()
        d = self.callRemote("setFrequency", value)
        d.addErrback(self.warningFailure)

    def stateSet(self, state, key, value):
        handler = self.uiStateHandlers.get(key, None)
        if handler:
            handler(value)

    def wave_changed_cb(self, widget):
        waveName = widget.get_active()
        d = self.callRemote("setWave", waveName)
        d.addErrback(self.warningFailure)

    def samplerateSet(self, samplerate):
        self._scale.set_range(1, samplerate)
        self._spinbutton.set_range(1, samplerate)

    def frequencySet(self, value):
        #self._scale.handler_block(self._scale_change_id)
        self._scale.set_value(value)
        #self._scale.handler_unblock(self._scale_change_id)
        #self._spinbutton.handler_block(self._spinbutton_change_id)
        self._spinbutton.set_value(value)
        #self._spinbutton.handler_unblock(self._spinbutton_change_id)

    def waveSet(self, value):
        #self._combobox.handler_block(self._combobox_change_id)
        self._combobox.set_active(value)
        #self._combobox.handler_unblock(self._combobox_change_id)


class AudioTestAdminGtk(BaseAdminGtk):

    def setup(self):
        volume = VolumeAdminGtkNode(self.state, self.admin,
                                    'volume', title=_("Volume"))
        self.nodes['Volume'] = volume
        audiotest = AudioTestAdminGtkNode(self.state, self.admin,
                                          title=_("Audio Test"))
        self.nodes['Audio Test'] = audiotest
        return BaseAdminGtk.setup(self)
