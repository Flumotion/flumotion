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

import gettext
import os

from zope.interface import implements

from flumotion.admin.assistant.interfaces import IProducerPlugin
from flumotion.admin.assistant.models import AudioProducer
from flumotion.common.errors import RemoteRunFailure
from flumotion.common.i18n import N_, gettexter
from flumotion.common.messages import Info
from flumotion.admin.gtk.basesteps import AudioProducerStep

__version__ = "$Rev$"
_ = gettext.gettext
T_ = gettexter()

CHANNELS = {1: _('Mono'),
            2: _('Stereo')}

SAMPLE_RATES = [48000,
                44100,
                32000,
                22050,
                16000,
                11025,
                8000]

# TODO: Add other sources (pulse, jack, ...)
SOURCE_ELEMENTS = [(_('Alsa'), 'alsasrc'),
                   (_('OSS'), 'osssrc')]


class SoundcardProducer(AudioProducer):
    componentType = 'soundcard-producer'

    def __init__(self):
        super(SoundcardProducer, self).__init__()


class SoundcardStep(AudioProducerStep):
    name = 'Soundcard'
    title = _('Sound Card')
    icon = 'soundcard.png'
    gladeFile = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              'wizard.glade')
    componentType = 'osssrc'
    docSection = 'help-configuration-assistant-producer-audio-soundcard'
    docAnchor = ''

    def __init__(self, wizard, model):
        AudioProducerStep.__init__(self, wizard, model)

    # WizardStep

    def setup(self):
        self.input_track.data_type = str
        self.channels.data_type = int
        self.samplerate.data_type = int
        self.depth.data_type = int
        self.device.data_type = str
        self.source_element.data_type = str

        self.source_element.prefill(SOURCE_ELEMENTS)

        self.add_proxy(self.model.properties,
                       ['input_track',
                        'channels',
                        'samplerate',
                        'depth',
                        'device',
                        'source_element'])

        # Connect the callback after the combo has been filled so the changed
        # signal is not emited before the page has been set uhas
        self.source_element.connect('changed', self.on_source_element__changed)

    def workerChanged(self, worker):
        self.model.worker = worker
        self._blockCombos()
        self._updateDevices()

    def getNext(self):
        return None

    # Private

    def _blockCombos(self, block=True):
        self.input_track.set_sensitive(not block)
        self.channels.set_sensitive(not block)
        self.depth.set_sensitive(not block)
        self.samplerate.set_sensitive(not block)

    def _updateDevices(self):
        self.wizard.waitForTask('soundcard checks')
        self.wizard.clear_msg('soundcard-check')

        msg = Info(T_(
            N_("Looking for the sound devices present on the system. "
               "This can take a while...")), mid='soundcard-check')
        self.wizard.add_msg(msg)

        def checkFailed(failure):
            failure.trap(RemoteRunFailure)
            self.wizard.taskFinished(blockNext=True)
            self._blockCombos()

        def gotSoundDevices(devices):
            self.wizard.clear_msg('soundcard-check')
            self.wizard.taskFinished(False)
            self.device.set_sensitive(True)
            self.device.prefill(devices)

        sourceElement = self.source_element.get_selected()

        d = self.runInWorker(
            'flumotion.worker.checks.audio', 'getAudioDevices',
            sourceElement, mid='soundcard-check')

        d.addCallback(gotSoundDevices)
        d.addErrback(checkFailed)

        return d

    def _updateInputtrack(self):
        device = self.device.get_selected()
        sourceElement = self.source_element.get_selected()

        if not device:
            return

        self.wizard.waitForTask('soundcard checks')
        msg = Info(T_(
            N_("Probing the sound card. This can take a while...")),
            mid='soundcard-check')
        self.wizard.add_msg(msg)

        def checkFailed(failure):
            failure.trap(RemoteRunFailure)
            self._blockCombos()
            self.wizard.taskFinished(True)

        def soundcardCheckComplete((deviceName, tracks, caps)):
            self.wizard.clear_msg('soundcard-check')
            self.wizard.taskFinished(False)
            self._caps = caps
            self.input_track.prefill(tracks)
            self.input_track.set_sensitive(bool(tracks))

        d = self.runInWorker(
            'flumotion.worker.checks.audio', 'checkMixerTracks',
            sourceElement, device, mid='soundcard-check')

        d.addCallback(soundcardCheckComplete)
        d.addErrback(checkFailed)

        return d

    def _updateDepth(self):
        bitdepths = {}
        for capStruct in self._caps:
            data = capStruct.copy()
            bitdepths[data.pop('depth')] = data
            self._capStructs = bitdepths
        bitdepths = sorted(bitdepths)
        self.depth.prefill(
        [(_('%d-bit') % bitdepth, bitdepth) for bitdepth in bitdepths])
        self.depth.set_sensitive(True)

    def _updateChannels(self):
        capStruct = self._capStructs.get(self.depth.get_selected())
        if capStruct is None:
            return
        channels = []
        if type(capStruct['channels']) == int:
            nchannels = capStruct['channels']
            channels.append((CHANNELS[nchannels], nchannels))
        else:
            for nchannels in capStruct['channels']:
                channels.append((CHANNELS[nchannels], nchannels))

        self.channels.prefill(channels)
        self.channels.set_sensitive(True)

    def _updateSamplerate(self):
        capStruct = self._capStructs.get(self.depth.get_selected())
        if capStruct is None:
            return
        if type(capStruct['rate']) == int:
            maxRate = minRate = capStruct['rate']
        else:
            maxRate, minRate = capStruct['rate']

        self.samplerate.prefill(
            [(str(rate), rate) for rate in SAMPLE_RATES
                if minRate <= rate <= maxRate])
        self.samplerate.set_sensitive(True)

    # Callbacks

    def on_source_element__changed(self, combo):
        self._updateDevices()

    def on_device__changed(self, combo):
        self._updateInputtrack()

    def on_input_track__changed(self, combo):
        self._updateDepth()
        self._updateChannels()

    def on_depth__changed(self, combo):
        self._updateSamplerate()


class SoundcardWizardPlugin(object):
    implements(IProducerPlugin)

    def __init__(self, wizard):
        self.wizard = wizard
        self.model = SoundcardProducer()

    def getProductionStep(self, type):
        return SoundcardStep(self.wizard, self.model)
