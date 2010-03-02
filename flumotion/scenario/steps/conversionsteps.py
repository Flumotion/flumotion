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
import re

from twisted.internet import defer

from flumotion.admin.assistant.models import AudioEncoder, VideoEncoder, Muxer
from flumotion.admin.gtk.workerstep import WorkerWizardStep
from flumotion.ui.wizard import WizardStep
from flumotion.common import errors, messages
from flumotion.common.i18n import N_, gettexter
from flumotion.scenario.steps.summarysteps import LiveSummaryStep

__version__ = "$Rev$"
_ = gettext.gettext
T_ = gettexter()

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
    docSection = 'help-configuration-assistant-encoders'
    docAnchor = ''
    docVersion = 'local'

    def __init__(self, wizard):
        WorkerWizardStep.__init__(self, wizard)
        self._muxer = None

    # Public API

    def getAudioPage(self):
        if self.wizard.getScenario().hasAudio(self.wizard):
            return self._getAudioPage()
        return None

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
        @returns: the muxer formats
        @rtype: string
        """
        entry = self.muxer.get_selected()
        return entry.getProvidedMediaTypes()[0]

    def getAudioFormat(self):
        """Returns the format of the audio encoder, such as "vorbis"
        @returns: the audio format
        @rtype: string
        """
        if self.wizard.getScenario().getAudioEncoder():
            entry = self.audio.get_selected()
            return entry.getProvidedMediaTypes()[0]

    def getVideoFormat(self):
        """Returns the format of the video encoder, such as "theora"
        @returns: the video format
        @rtype: string
        """
        if self.wizard.getScenario().getVideoEncoder():
            entry = self.video.get_selected()
            return entry.getProvidedMediaTypes()[0]

    # WizardStep

    def activated(self):
        data = [('muxer', self.muxer, None, None)]

        if self.wizard.getScenario().hasAudio(self.wizard):
            oldAudioEncoder = self.wizard.getScenario().getAudioEncoder()
            data.append(('audio-encoder', self.audio,
                         _PREFERRED_AUDIO_ENCODER,
                         oldAudioEncoder))
        else:
            self.audio.hide()
            self.label_audio.hide()
            self.wizard.getScenario().setAudioEncoder(None)

        if self.wizard.getScenario().hasVideo(self.wizard):
            oldVideoEncoder = self.wizard.getScenario().getVideoEncoder()
            data.append(('video-encoder', self.video,
                         _PREFERRED_VIDEO_ENCODER,
                         oldVideoEncoder))
        else:
            self.video.hide()
            self.label_video.hide()
            self.wizard.getScenario().setVideoEncoder(None)


        # If there is data in the combo already, do not populate it,
        # Because it means we're pressing "back" in the wizard and the
        # combo is already populated.
        hasVideo = len(self.video) > 0
        hasAudio = len(self.audio) > 0

        if not hasVideo or not hasAudio:
            self._populateCombos(data)

    def getNext(self):
        #TODO: Share in some way this code with the productionsteps page.
        if self.wizard.getScenario().hasVideo(self.wizard):
            return self._getVideoPage()
        elif self.wizard.getScenario().hasAudio(self.wizard):
            return self._getAudioPage()
        else:
            raise AssertionError

    def workerChanged(self, worker):
        if self._muxer:
            self._muxer.workerChanged(worker)

    # Private

    def _populateCombos(self, combos, provides=None):
        self.debug("populating combos %r", combos)
        self.wizard.waitForTask('querying encoders')

        defers = []
        for ctype, combo, defaultType, oldComponent in combos:
            combo.prefill([('...', None)])
            combo.set_sensitive(False)

            d = self.wizard.getWizardEntries(
                wizardTypes=[ctype],
                provides=provides)
            d.addCallback(self._addEntries, ctype, combo, defaultType,
                          oldComponent)
            defers.append(d)

        d = defer.DeferredList(defers)
        d.addCallback(lambda x: self.wizard.taskFinished())
        return d

    def _canAddMuxer(self, entry):
        # Fetch the media types the muxer accepts ('audio', 'video')
        types = [t.split(':')[0] for t in entry.getAcceptedMediaTypes()]

        acceptAudio = 'audio' in types
        acceptVideo = 'video' in types

        if acceptVideo ^ acceptAudio:
            hasAudio = self.wizard.getScenario().hasAudio(self.wizard)
            hasVideo = self.wizard.getScenario().hasVideo(self.wizard)
            if hasAudio and not acceptAudio or hasVideo and not acceptVideo:
                return False

        return True

    def _addEntries(self, entries, ctype, combo, defaultType, oldComponent):
        self.debug('adding entries for ctype %s: %r with defaultType %s',
                   ctype, entries, defaultType)
        data = []
        for entry in entries:
            if ctype != 'muxer' or self._canAddMuxer(entry):
                item = (N_(entry.description), entry)
                providedMediaTypes = entry.getProvidedMediaTypes()
                self.debug("adding entry %r", providedMediaTypes)

                if defaultType and defaultType in providedMediaTypes:
                    data.insert(0, item)
                else:
                    data.append(item)

        combo.prefill(data)
        combo.set_sensitive(True)

        if oldComponent:
            for description, entry in combo.get_model_items().iteritems():
                if entry.componentType == oldComponent.componentType:
                    combo.select(entry)
                    break

    def _loadPlugin(self, entry):

        def gotFactory(factory):
            return factory(self.wizard)

        def no_bundle(failure):
            failure.trap(errors.NoBundleError)

        d = self.wizard.getWizardEntry(entry.componentType)
        d.addCallback(gotFactory)
        d.addErrback(no_bundle)

        return d

    def _loadStep(self, combo):

        def pluginLoaded(plugin, entry):
            # FIXME: verify that factory implements IEncoderPlugin
            step = plugin.getConversionStep()
            return step

        entry = combo.get_selected()
        d = self._loadPlugin(entry)
        d.addCallback(pluginLoaded, entry)
        return d

    def _getAudioPage(self):

        def stepLoaded(step):
            if step is not None:
                self.wizard.getScenario().setAudioEncoder(step.model)
            self.wizard.taskFinished()
            return step
        self.wizard.waitForTask('audio encoder page')
        d = self._loadStep(self.audio)
        d.addCallback(stepLoaded)
        return d

    def _getVideoPage(self):

        def stepLoaded(step):
            if step is not None:
                self.wizard.getScenario().setVideoEncoder(step.model)
            self.wizard.taskFinished()
            return step
        self.wizard.waitForTask('video encoder page')
        d = self._loadStep(self.video)
        d.addCallback(stepLoaded)
        return d

    def _muxerChanged(self):
        muxerEntry = self.muxer.get_selected()
        self.wizard.message_area.clear()
        # '...' used while waiting for the query to be done
        if muxerEntry is None:
            return

        def combosPopulated(unused):
            return self._loadPlugin(muxerEntry)

        def pluginLoaded(plugin, entry):
            if plugin:
                self._muxer = plugin
                return plugin.workerChanged(self.worker)
            else:
                # no plugin defined, behaving like before
                # FIXME: make check should make sure all muxers have a
                # plugin/factory and fail if not
                self.wizard.clear_msg('assistant-bundle')
                self.wizard.taskFinished()

        provides = map(lambda f: f.find(':') > 0 and f.split(':', 1)[1] or f,
                       muxerEntry.getAcceptedMediaTypes())
        d = self._populateCombos(
            [('audio-encoder', self.audio, _PREFERRED_AUDIO_ENCODER,
              self.wizard.getScenario().getAudioEncoder()),
             ('video-encoder', self.video, _PREFERRED_VIDEO_ENCODER,
              self.wizard.getScenario().getVideoEncoder())],
            provides=provides)
        d.addCallback(combosPopulated)
        d.addCallback(pluginLoaded, muxerEntry)
        return d

    # Callbacks

    def on_muxer__changed(self, combo):
        self._muxerChanged()


class SelectFormatStep(WizardStep):
    name = 'Encoding'
    title = _('Select Format')
    section = _('Format')
    gladeFile = 'encoding-wizard.glade'
    docSection = 'help-configuration-assistant-encoders'
    docAnchor = ''
    docVersion = 'local'
    # Public API

    def setMuxers(self, muxers):
        self._muxers = [muxer for muxer in muxers]

    def getMuxerFormat(self):
        """Returns the format of the muxer, such as "ogg".
        @returns: the muxer formats
        @rtype: string
        """
        muxer = self.muxer.get_selected()
        if not muxer:
            return

        entry = self._entries[muxer.componentType]
        return entry.getProvidedMediaTypes()[0]

    def getMuxerType(self):
        """Returns the component-type, such as "ogg-muxer"
        of the currently selected muxer.
        @returns: the muxer
        @rtype: string
        """
        muxer = self.muxer.get_selected()
        if not muxer:
            return

        entry = self._entries[muxer.componentType]
        return entry.componentType

    def getAudioFormat(self):
        """Returns the format of the audio encoder, such as "vorbis"
        @returns: the audio format
        @rtype: string
        """
        return None

    def getVideoFormat(self):
        """Returns the format of the video encoder, such as "theora"
        @returns: the video format
        @rtype: string
        """
        return None

    # WizardStep

    def activated(self):
        self.audio.hide()
        self.label_audio.hide()
        self.wizard.getScenario().setAudioEncoder(None)
        self.video.hide()
        self.label_video.hide()
        self.wizard.getScenario().setVideoEncoder(None)

        self._populateCombo()

    def _populateCombo(self):
        self.debug("populating muxer combo")
        self.wizard.waitForTask('get entries')
        d = self.wizard.getWizardEntries(wizardTypes=['muxer'])
        d.addCallback(self._addEntries)
        self.muxer.prefill([('...', None)])
        d.addCallback(lambda x: self.wizard.taskFinished() and
                      self.muxer.set_sensitive(True))

    def _addEntries(self, entries):
        data = []
        self._entries = \
                dict([(entry.componentType, entry) for entry in entries])
        for muxer in self._muxers:
            pattern = re.compile('^muxer-(.*?)\d*$')
            match = pattern.search(muxer.name)
            muxer.type = match.group(1)

            desc = '%s (%s)' % (N_(muxer.description), muxer.name)
            data.append((desc, muxer))

        self.muxer.prefill(data)

    def getNext(self):
        # Return audio/video/audio-video http streamer page
        from flumotion.scenario.steps.httpstreamersteps import HTTPBothStep, \
                HTTPAudioStep, HTTPVideoStep, HTTPGenericStep
        self.wizard.cleanFutureSteps()
        muxer = self.muxer.get_selected()

        if muxer.type == 'audio-video':
            self.wizard.addStepSection(HTTPBothStep(self.wizard))
        elif muxer.type == 'video':
            self.wizard.addStepSection(HTTPVideoStep(self.wizard))
        elif muxer.type == 'audio':
            self.wizard.addStepSection(HTTPAudioStep(self.wizard))
        else:
            self.wizard.addStepSection(HTTPGenericStep(self.wizard,
                                                       muxer.type))

        self.wizard.addStepSection(LiveSummaryStep)

    # Callbacks

    def on_muxer__changed(self, combo):
        muxer = combo.get_selected()
        if not muxer:
            return

        self.wizard.getScenario().setExistingMuxer(muxer)
