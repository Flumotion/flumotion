# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006 Fluendo, S.L. (www.fluendo.com).
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

from gettext import gettext as _

from flumotion.component.base import admin_gtk
from flumotion.component.effects.volume import admin_gtk as vadmin_gtk

class AudioTestAdminGtkNode(admin_gtk.BaseAdminGtkNode):
    logCategory = 'audiotest'
    def render(self):
        self.debug('rendering audiotest node')
        file = 'flumotion/component/producers/audiotest/audiotest.glade'
        d = self.loadGladeFile(file)
        d.addCallback(self._loadGladeFileCallback)

        return d

    def _loadGladeFileCallback(self, widgetTree):
        self.wtree = widgetTree
        self.widget = self.wtree.get_widget('widget-audiotest')

        d = self.callRemote("getAudioTestProperties")
        d.addCallback(self.getAudioTestPropertiesCallback)
        d.addErrback(self.warningFailure)
        d.addCallback(lambda result: self.widget)

        return d

    def getAudioTestPropertiesCallback(self, result):
        waveNames, wave, frequency, maximumFrequency = result
        self._scale = self.wtree.get_widget('scale-frequency')
        self._spinbutton = self.wtree.get_widget('spinbutton-frequency')
        self._combobox = self.wtree.get_widget('combobox-wave')

        self._scale.set_value(frequency)
        self._scale.set_range(1, maximumFrequency)
        self._spinbutton.set_value(frequency)
        self._spinbutton.set_range(1, maximumFrequency)
        self._combobox.set_active(wave)

        self._scale_change_id = self._scale.connect('value-changed',
            self.frequency_changed_cb)
        self._spinbutton_change_id = self._spinbutton.connect('value-changed',
            self.frequency_changed_cb)
        self._combobox_change_id = self._combobox.connect('changed',
            self.wave_changed_cb)

    def getAudioTestPropertiesErrback(self, failure):
        self.warning("Failure %s getting audio test properties: %s" % (
            failure.type, failure.getErrorMessage()))
        return None

    def frequency_changed_cb(self, widget):
        value = widget.get_value()
        self.frequencyChanged(value)
        d = self.callRemote("setFrequency", value)
        d.addErrback(self.warningFailure)

    def wave_changed_cb(self, widget):
        waveName = widget.get_active()
        d = self.callRemote("setWave", waveName)
        d.addErrback(self.warningFailure)
        
    def frequencyChanged(self, value):
        if self._scale_change_id != -1:
            self.debug('scale_change_id not -1, setting freq to value %r' %
                value)
            self._scale.handler_block(self._scale_change_id)
            self._scale.set_value(value)
            self._scale.handler_unblock(self._scale_change_id)
            self._spinbutton.handler_block(self._spinbutton_change_id)
            self._spinbutton.set_value(value)
            self._spinbutton.handler_unblock(self._spinbutton_change_id)

    def waveChanged(self, value):
        if self._combobox_change_id != -1:
            self._combobox.handler_block(self._combobox_change_id)
            self._combobox.set_active(value)
            self._combobox.handler_unblock(self._combobox_change_id)

class AudioTestAdminGtk(admin_gtk.BaseAdminGtk):
    def setup(self):
        self._nodes = {}
        volume = vadmin_gtk.VolumeAdminGtkNode(self.state, self.admin,
                                               'volume', title=_("Volume"))
        self._nodes['Volume'] = volume
        audiotest = AudioTestAdminGtkNode(self.state, self.admin,
                                          title=_("Audio Test"))
        self._nodes['Audio Test'] = audiotest

    def getNodes(self):
        return self._nodes

    def component_frequencyChanged(self, frequency):
        self.debug('component tells me frequency changed to %d Hz' % frequency)
        node = self._nodes['Audio Test']
        node.frequencyChanged(frequency)

    def component_waveChanged(self, wave):
        node = self._nodes['Audio Test']
        node.waveChanged(wave)

    def component_volumeChanged(self, channel, rms, peak, decay):
        volume = self._nodes['Volume']
        volume.volumeChanged(channel, rms, peak, decay)

    def component_effectVolumeSet(self, effect, volume):
        """
        @param volume: volume multiplier between 0.0 and 4.0
        @type  volume: float
        """
        if effect != 'volume':
            self.warning('Unknown effect %s in %r' % (effect, self))
            return
        v = self._nodes['Volume']
        v.volumeSet(volume)
