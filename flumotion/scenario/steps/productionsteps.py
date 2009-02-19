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

import gtk

from flumotion.common.errors import NoBundleError
from flumotion.common.i18n import N_
from flumotion.ui.wizard import WizardStep

# Register components
from flumotion.common import componentui

__version__ = "$Rev$"
# pychecker doesn't like the auto-generated widget attrs
# or the extra args we name in callbacks
__pychecker__ = 'no-classattr no-argsused'
_ = gettext.gettext


class LiveProductionStep(WizardStep):
    """This step is showing a list of available audio and video production
    components. The list of component are queried from the manager
    by a remote call (getWizardEntries) which will populate the combos.
    """
    name = 'Production'
    title = _('Production')
    section = _('Production')
    icon = 'source.png'
    gladeFile = 'production-wizard.glade'
    docSection = 'help-configuration-assistant-production'
    docAnchor = ''
    docVersion = 'local'

    def __init__(self, wizard):
        self._audioProducer = None
        self._videoProducer = None
        self._loadedSteps = None
        WizardStep.__init__(self, wizard)

    # Public API

    def hasAudio(self):
        """Returns if audio will be used in the stream
        created by the wizard.

        @returns: if audio will be used
        @rtype:   bool
        """
        return self.has_audio.get_active()

    def hasVideo(self):
        """Returns if video will be used in the stream
        created by the wizard.

        @returns: if video will be used
        @rtype:   bool
        """
        return self.has_video.get_active()

    def getAudioProducer(self):
        """Returns the selected audio producer or None
        @returns: producer or None
        @rtype: L{flumotion.admin.assistant.models.AudioProducer}
        """
        if self.has_audio.get_active():
            return self._audioProducer

    def getVideoProducer(self):
        """Returns the selected video producer or None
        @returns: producer or None
        @rtype: L{flumotion.admin.assistant.models.VideoProducer}
        """
        if self.has_video.get_active():
            return self._videoProducer

    def getVideoStep(self):
        """Return the video step to be shown, given the currently
        selected values in this step
        @returns: video step
        @rtype: a deferred returning a L{basesteps.VideoProducerStep} instance
        """

        def stepLoaded(step):
            if step is not None:
                self._videoProducer = step.model
            self.wizard.taskFinished()
            return step
        self.wizard.waitForTask('video producer step')
        d = self._loadStep(self.video, 'video')
        d.addCallback(stepLoaded)
        return d

    def getAudioStep(self):
        """Return the audio step to be shown, given the currently
        selected values in this step
        @returns: audio step
        @rtype: a deferred returning a L{basesteps.AudioProducerStep} instance
        """

        def stepLoaded(step):
            if step is not None:
                self._audioProducer = step.model
            self.wizard.taskFinished()
            return step
        self.wizard.waitForTask('audio producer step')
        d = self._loadStep(self.audio, 'audio')
        d.addCallback(stepLoaded)
        return d

    # WizardStep

    def setup(self):
        self.audio.data_type = object
        self.video.data_type = object
        # We want to save the audio/video attributes as
        # componentType in the respective models
        self.audio.model_attribute = 'componentType'
        self.video.model_attribute = 'componentType'

        tips = gtk.Tooltips()
        tips.set_tip(self.has_video,
            _('Select this if you want to stream video'))
        tips.set_tip(self.has_audio,
            _('Select this if you want to stream audio'))

        self._populateCombos()

    def getNext(self):
        #TODO: Share in some way this code with the conversionsteps page.
        if self.hasVideo():
            return self.getVideoStep()
        elif self.hasAudio():
            return self.getAudioStep()
        else:
            raise AssertionError

    # Private API

    def _populateCombos(self):

        def gotEntries(entries, combo, default_type):
            data = []
            default = None
            for entry in entries:
                if entry.componentType == default_type:
                    default = entry
                    continue
                data.append((N_(entry.description), entry.componentType))
            assert default
            data.insert(0, (N_(default.description), default.componentType))
            combo.prefill(data)
            combo.set_sensitive(True)

        for ctype, combo, default_type in [
            ('video-producer', self.video, 'videotest-producer'),
            ('audio-producer', self.audio, 'audiotest-producer')]:
            d = self.wizard.getWizardEntries(
                wizardTypes=[ctype])
            d.addCallback(gotEntries, combo, default_type)
            combo.prefill([('...', None)])
            combo.set_sensitive(False)

        self.wizard.waitForTask('querying producers')

        def done(_):
            self.wizard.taskFinished()
            self._loadedSteps = True
        d.addCallback(done)

    def _loadPlugin(self, componentType, type):

        def gotFactory(factory):
            return factory(self.wizard)

        def noBundle(failure):
            failure.trap(NoBundleError)

        d = self.wizard.getWizardEntry(componentType)
        d.addCallback(gotFactory)
        d.addErrback(noBundle)

        return d

    def _loadStep(self, combo, type):

        def pluginLoaded(plugin, entry):
            # FIXME: verify that factory implements IProductionPlugin
            step = plugin.getProductionStep(type)
            return step

        entry = combo.get_selected()
        d = self._loadPlugin(entry, type)
        d.addCallback(pluginLoaded, entry)

        return d

    def _verify(self):
        if not self._loadedSteps:
            return

        canContinue = self.hasAudio() or self.hasVideo()
        self.wizard.blockNext(not canContinue)

    # Callbacks

    def on_has_video__toggled(self, button):
        self.video.set_sensitive(button.get_active())
        self._verify()

    def on_has_audio__toggled(self, button):
        self.audio.set_sensitive(button.get_active())
        self._verify()

    def on_video__changed(self, button):
        self._verify()

    def on_audio__changed(self, button):
        self._verify()


class SelectProducersStep(WizardStep):
    name = 'Production'
    title = _('Production')
    section = _('Production')
    icon = 'source.png'
    gladeFile = 'select-producers-wizard.glade'

    def __init__(self, wizard):
        self._audioProducer = None
        self._videoProducer = None
        self._loadedSteps = None
        WizardStep.__init__(self, wizard)

    # Public API

    def hasAudio(self):
        """Returns if audio will be used in the stream
        created by the wizard.

        @returns: if audio will be used
        @rtype:   bool
        """
        return self.has_audio.get_active()

    def hasVideo(self):
        """Returns if video will be used in the stream
        created by the wizard.

        @returns: if video will be used
        @rtype:   bool
        """
        return self.has_video.get_active()

    def getAudioProducer(self):
        """Returns the selected audio producer or None
        @returns: producer or None
        @rtype: L{flumotion.admin.assistant.models.AudioProducer}
        """
        if self.has_audio.get_active():
            return self.audio.get_selected()

    def getVideoProducer(self):
        """Returns the selected video producer or None
        @returns: producer or None
        @rtype: L{flumotion.admin.assistant.models.VideoProducer}
        """
        if self.has_video.get_active():
            return self.video.get_selected()

    def setVideoProducers(self, videoProducers):
        self.video.prefill([(N_(vp.description), vp) for vp in videoProducers])
        self._updateWidgets()

    def setAudioProducers(self, audioProducers):
        self.audio.prefill([(N_(vp.description), vp) for vp in audioProducers])
        self._updateWidgets()

    # WizardStep

    def setup(self):
        self.audio.data_type = object
        self.video.data_type = object
        # We want to save the audio/video attributes as
        # componentType in the respective models
        self.audio.model_attribute = 'componentType'
        self.video.model_attribute = 'componentType'

        tips = gtk.Tooltips()
        tips.set_tip(self.has_video,
            _('Select this if you want to stream video'))
        tips.set_tip(self.has_audio,
            _('Select this if you want to stream audio'))

    def getNext(self):
        return None

    # Private API

    def _updateWidgets(self):
        # We can't call getAudio/VideoProducer here, since they
        # depend on set_active() being enabled
        hasAudio = bool(self.audio.get_model_strings())
        hasVideo = bool(self.video.get_model_strings())
        hasBoth = hasVideo and hasAudio
        self.has_video.set_active(hasVideo)
        self.has_audio.set_active(hasAudio)
        self.audio.set_property('visible', hasAudio)
        self.video.set_property('visible', hasVideo)
        self.has_audio.set_property('visible', hasBoth)
        self.has_video.set_property('visible', hasBoth)

    def _verify(self):
        canContinue = self.hasAudio() or self.hasVideo()
        self.wizard.blockNext(not canContinue)

    # Callbacks

    def on_has_video__toggled(self, button):
        self.video.set_sensitive(button.get_active())
        self._verify()

    def on_has_audio__toggled(self, button):
        self.audio.set_sensitive(button.get_active())
        self._verify()

    def on_video__changed(self, button):
        self._verify()

    def on_audio__changed(self, button):
        self._verify()
