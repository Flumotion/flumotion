# -*- Mode: Python -*-
# vi:si:et:sw=4:sts=4:ts=4
#
# Flumotion - a streaming media server
# Copyright (C) 2004,2005,2006,2007,2008 Fluendo, S.L. (www.fluendo.com).
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

import gettext
import os

from zope.interface import implements

from flumotion.common import enum
from flumotion.common.messages import N_, gettexter, Info
from flumotion.wizard.basesteps import AudioProducerStep
from flumotion.wizard.interfaces import IProducerPlugin
from flumotion.wizard.models import AudioProducer

__version__ = "$Rev$"
_ = gettext.gettext
T_ = gettexter('flumotion')

OSS_DEVICES = ["/dev/dsp",
               "/dev/dsp1",
               "/dev/dsp2"]
ALSA_DEVICES = ['hw:0',
                'hw:1',
                'hw:2']
CHANNELS = [(_('Stereo'), 2),
            (_('Mono'), 1)]
BITDEPTHS = [(_('16-bit'), 16)]
SAMPLE_RATES = [48000,
                44100,
                32000,
                22050,
                16000,
                11025,
                8000]
SoundcardSystem = enum.EnumClass(
    'SoundcardSystem',
    ['Alsa', 'OSS'],
    element_name=['alsasrc', 'osssrc'])


class SoundcardProducer(AudioProducer):
    component_type = 'soundcard-producer'

    def __init__(self):
        super(SoundcardProducer, self).__init__()

        self.properties.input_track = ''
        self.properties.channels = 2
        self.properties.rate = 44100
        self.properties.depth = 16
        self.properties.device = ''
        self.properties.source_element = 'alsasrc'


class SoundcardStep(AudioProducerStep):
    name = _('Soundcard')
    glade_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'soundcard-wizard.glade')
    component_type = 'osssrc'
    icon = 'soundcard.png'

    def __init__(self, wizard, model):
        AudioProducerStep.__init__(self, wizard, model)
        self._block_update = False

    # WizardStep

    def setup(self):
        # block updates, because populating a shown combobox will of course
        # trigger the callback
        self._block_update = True
        self.input_track.data_type = str
        self.channels.data_type = int
        self.rate.data_type = int
        self.depth.data_type = int
        self.device.data_type = str
        self.source_element.data_type = str

        self.input_track.prefill([''])
        self.channels.prefill(CHANNELS)
        self.rate.prefill([(str(r), r) for r in SAMPLE_RATES])
        self.depth.prefill(BITDEPTHS)
        self.device.prefill([''])
        self.source_element.prefill(
            [(enum.nick, enum.element_name) for enum in SoundcardSystem])

        self.add_proxy(self.model.properties,
                       ['input_track',
                        'channels',
                        'rate',
                        'depth',
                        'device',
                        'source_element'])

        self._block_update = False

    def worker_changed(self, worker):
        self.model.worker = worker
        self._clear_combos()
        self._update_devices()
        self._update_inputs()

    def get_next(self):
        return None

    # Private

    def _clear_combos(self):
        self.input_track.clear()
        self.input_track.set_sensitive(False)
        self.channels.set_sensitive(False)
        self.rate.set_sensitive(False)
        self.depth.set_sensitive(False)

    def _update_devices(self):
        self._block_update = True
        self.device.clear()
        enum = self.source_element.get_selected()
        if enum == SoundcardSystem.Alsa.element_name:
            self.device.prefill(ALSA_DEVICES)
        elif enum == SoundcardSystem.OSS.element_name:
            self.device.prefill(OSS_DEVICES)
        else:
            raise AssertionError
        self._block_update = False

    def _update_inputs(self):
        if self._block_update:
            return
        self.wizard.block_next(True)

        device = self.device.get_selected()
        element_name = self.source_element.get_selected()
        channels = self.channels.get_selected() or 2
        assert device
        assert element_name
        assert channels
        msg = Info(T_(
            N_("Probing soundcard, this can take a while...")),
                            id='soundcard-check')
        self.wizard.add_msg(msg)
        d = self.run_in_worker(
            'flumotion.worker.checks.audio', 'checkMixerTracks',
            element_name, device, channels, id='soundcard-check')

        def checkFailed(failure):
            self._clear_combos()
            self.wizard.block_next(True)

        def soundcardCheckComplete((deviceName, tracks)):
            self.wizard.clear_msg('soundcard-check')
            self.wizard.block_next(False)
            self.label_devicename.set_label(deviceName)
            self._block_update = True
            self.channels.set_sensitive(True)
            self.rate.set_sensitive(True)
            self.depth.set_sensitive(True)
            self.input_track.prefill(tracks)
            self.input_track.set_sensitive(bool(tracks))
            self._block_update = False

        d.addCallback(soundcardCheckComplete)
        d.addErrback(checkFailed)

        return d

    # Callbacks

    def on_source_element__changed(self, combo):
        if not self._block_update:
            self._update_devices()
            self._update_inputs()

    def on_device__changed(self, combo):
        self._update_inputs()

    def on_channels__changed(self, combo):
        # FIXME: make it so that the number of channels can be changed
        # and the check gets executed with the new number
        # self.update_inputs()
        pass


class SoundcardWizardPlugin(object):
    implements(IProducerPlugin)
    def __init__(self, wizard):
        self.wizard = wizard
        self.model = SoundcardProducer()

    def getProductionStep(self, type):
        return SoundcardStep(self.wizard, self.model)

