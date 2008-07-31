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

from flumotion.common.errors import NoBundleError
from flumotion.common.i18n import N_
from flumotion.wizard.models import AudioEncoder, VideoEncoder, Muxer
from flumotion.wizard.workerstep import WorkerWizardStep

__version__ = "$Rev$"
_ = gettext.gettext

_PREFERRED_VIDEO_ENCODER = "theora"
_PREFERRED_AUDIO_ENCODER = "vorbis"

# the denominator arg for all calls of this function was sniffed from
# the glade file's spinbutton adjustment

def _fraction_from_float(number, denominator):
    """
    Return a string to be used in serializing to XML.
    """
    return "%d/%d" % (number * denominator, denominator)


class ConversionStep(WorkerWizardStep):
    name = 'Encoding'
    title = _('Encoding')
    section = _('Conversion')
    gladeFile = 'encoding-wizard.glade'
    docSection = 'chapter-using-assistant'
    docAnchor = 'figure-configure-assistant-encoders'
    docVersion = 'local'

    def __init__(self, wizard):
        self._audioEncoder = None
        self._videoEncoder = None
        WorkerWizardStep.__init__(self, wizard)

    # Public API

    def getAudioPage(self):
        if self.wizard.hasAudio():
            return self._getAudioPage()
        return None

    def getVideoEncoder(self):
        """Returns the selected video encoder or None
        @returns: encoder or None
        @rtype: L{flumotion.wizard.models.VideoEncoder}
        """
        return self._videoEncoder

    def getAudioEncoder(self):
        """Returns the selected audio encoder or None
        @returns: encoder or None
        @rtype: L{flumotion.wizard.models.AudioEncoder}
        """
        return self._audioEncoder

    def getMuxerType(self):
        """Returns the component-type, such as "ogg-muxer"
        of the currently selected muxer.
        @returns: the muxer
        @rtype: string
        """
        entry = self.muxer.get_selected()
        return entry.componentType

    def getMuxerFormat(self):
        """Returns the format of the muxer, such as "ogg".
        @returns: the muxer format
        @rtype: string
        """
        entry = self.muxer.get_selected()
        return entry.getProvidedMediaTypes()[0]

    def getAudioFormat(self):
        """Returns the format of the audio encoder, such as "vorbis"
        @returns: the audio format
        @rtype: string
        """
        if self._audioEncoder:
            entry = self.audio.get_selected()
            return entry.getProvidedMediaTypes()[0]

    def getVideoFormat(self):
        """Returns the format of the video encoder, such as "theora"
        @returns: the video format
        @rtype: string
        """
        if self._videoEncoder:
            entry = self.video.get_selected()
            return entry.getProvidedMediaTypes()[0]

    # WizardStep

    def activated(self):
        data = [('muxer', self.muxer, None)]

        audio_producer = self.wizard.getAudioProducer()
        if audio_producer:
            data.append(('audio-encoder', self.audio, _PREFERRED_AUDIO_ENCODER))
        else:
            self.audio.hide()
            self.label_audio.hide()

        video_producer = self.wizard.getVideoProducer()
        if video_producer:
            data.append(('video-encoder', self.video, _PREFERRED_VIDEO_ENCODER))
        else:
            self.video.hide()
            self.label_video.hide()

        # If there is data in the combo already, do not populate it,
        # Because it means we're pressing "back" in the wizard and the
        # combo is already populated.
        if not len(self.video) or not len(self.audio):
            self._populateCombos(data)

    def getNext(self):
        if self.wizard.hasVideo():
            return self._getVideoPage()
        elif self.wizard.hasAudio():
            return self._getAudioPage()
        else:
            raise AssertionError

    # Private

    def _populateCombos(self, combos, provides=None):
        self.debug("populating combos %r", combos)
        for ctype, combo, default_type in combos:
            d = self.wizard.getWizardEntries(
                wizardTypes=[ctype],
                provides=provides)
            d.addCallback(self._addEntries, ctype, combo, default_type)
            combo.prefill([('...', None)])
            combo.set_sensitive(False)
        self.wizard.waitForTask('querying encoders')
        d.addCallback(lambda x: self.wizard.taskFinished())

    def _addEntries(self, entries, ctype, combo, default_type):
        self.debug('adding entries for ctype %s: %r with default_type %s', ctype, entries, default_type)
        data = []
        for entry in entries:
            item = (N_(entry.description), entry)
            provided_media_types = entry.getProvidedMediaTypes()
            self.debug("adding entry %r", provided_media_types)
            if default_type and default_type in provided_media_types:
                data.insert(0, item)
            else:
                data.append(item)
        combo.prefill(data)
        combo.set_sensitive(True)

    def _createDummyModel(self, entry):
        if entry.type == 'audio-encoder':
            encoder = AudioEncoder()
        elif entry.type == 'video-encoder':
            encoder = VideoEncoder()
        else:
            raise AssertionError

        encoder.componentType = entry.componentType
        encoder.worker = self.worker

        if entry.type == 'audio-encoder':
            self._audioEncoder = encoder
        else:
            self._videoEncoder = encoder

    def _loadPlugin(self, entry):
        def gotFactory(factory):
            return factory(self.wizard)

        def no_bundle(failure):
            failure.trap(NoBundleError)

        d = self.wizard.getWizardEntry(entry.componentType)
        d.addCallback(gotFactory)
        d.addErrback(no_bundle)

        return d

    def _loadStep(self, combo):
        entry = combo.get_selected()
        assert entry, 'combo %s has nothing selected' % (combo, )
        
        def pluginLoaded(plugin, entry):
            if plugin is None:
                self._createDummyModel(entry)
                return None
            # FIXME: verify that factory implements IEncoderPlugin
            step = plugin.getConversionStep()
            if isinstance(step, WorkerWizardStep):
                self.wizard.workerChangedForStep(step, self.worker)
            return step

        d = self._loadPlugin(entry)
        d.addCallback(pluginLoaded, entry)

        return d

    def _getAudioPage(self):
        def stepLoaded(step):
            if step is not None:
                self._audioEncoder = step.model
            self.wizard.taskFinished()
            return step
        self.wizard.waitForTask('audio encoder page')
        d = self._loadStep(self.audio)
        d.addCallback(stepLoaded)
        return d

    def _getVideoPage(self):
        def stepLoaded(step):
            if step is not None:
                self._videoEncoder = step.model
            self.wizard.taskFinished()
            return step
        self.wizard.waitForTask('video encoder page')
        d = self._loadStep(self.video)
        d.addCallback(stepLoaded)
        return d

    def _muxerChanged(self):
        muxer_entry = self.muxer.get_selected()
        # '...' used while waiting for the query to be done
        if muxer_entry is None:
            return
        self._populateCombos([('audio-encoder', self.audio, _PREFERRED_AUDIO_ENCODER),
                               ('video-encoder', self.video, _PREFERRED_VIDEO_ENCODER)],
                              provides=muxer_entry.getAcceptedMediaTypes())

    # Callbacks

    def on_muxer__changed(self, combo):
        self._muxerChanged()

