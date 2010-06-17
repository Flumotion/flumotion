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

from flumotion.admin.gtk.workerstep import WorkerWizardStep
from flumotion.common.i18n import N_
from flumotion.common.python import any as pany
from flumotion.common.errors import NoBundleError
from flumotion.configure import configure
from flumotion.ui.wizard import WizardStep

__version__ = "$Rev$"
_ = gettext.gettext

PREFERRED_CONSUMER = 'http-streamer'
CONSUMER_BOTH = [('audio-video', _('Audio & Video'))]
CONSUMER_VIDEO = [('video', _('Video only'))]
CONSUMER_AUDIO = [('audio', _('Audio only'))]


class ConsumptionStep(WizardStep):
    name = 'Consumption'
    title = _('Consumption')
    section = _('Consumption')
    icon = 'consumption.png'
    gladeFile = 'consumption-wizard.glade'
    docSection = 'help-configuration-assistant-consumption'
    docAnchor = ''
    docVersion = 'local'

    # WizardStep

    def setup(self):
        hasAudio = self.wizard.getScenario().hasAudio(self.wizard)
        hasVideo = self.wizard.getScenario().hasVideo(self.wizard)
        self._hasBoth = hasAudio and hasVideo

        self._buttons = {}
        self._consumerTypes = []
        self._stepsGen = None
        self._steplist = []
        if self._hasBoth:
            self._consumers = CONSUMER_BOTH + CONSUMER_VIDEO + CONSUMER_AUDIO
        elif hasAudio:
            self._consumers = CONSUMER_AUDIO
        elif hasVideo:
            self._consumers = CONSUMER_VIDEO

        self._populateField()

    def _gotEntries(self, entries):
        for entry in entries:
            if (entry.componentType == 'shout2-consumer' and
                not self._canEmbedShout()):
                continue
            hbox = gtk.HBox()
            vbox = gtk.VBox()
            for type, desc in self._consumers:
                consumer = "%s-%s" % (entry.componentType, type)
                self._packButtonToBox(vbox, consumer, desc)
                self._buttons[consumer].set_sensitive(False)

            hbox.pack_start(vbox, padding=24)

            vbox = gtk.VBox()
            self._packButtonToBox(vbox, entry.componentType,
                                  _(entry.description))
            self._consumerTypes.append(entry.componentType)

            vbox.pack_start(hbox)
            self.consumers.pack_start(vbox)

            if entry.componentType == PREFERRED_CONSUMER:
                self._consumerTypes.insert(0, self._consumerTypes.pop())
                self.consumers.reorder_child(vbox, 0)
                self._buttons[entry.componentType].set_active(True)

        self.consumers.show_all()
        self._verify()

    def _packButtonToBox(self, box, name, description):
        self._buttons[name] = gtk.CheckButton(label=description)
        self._buttons[name].connect('toggled',
                                    self.on_checkbutton_toggled, name)
        box.pack_start(self._buttons[name], expand=False, fill=False)

    def _populateField(self):
        d = self.wizard.getWizardEntries(wizardTypes=['consumer'])
        d.addCallback(self._gotEntries)
        return d

    def _loadStep(self, componentType, type):

        def gotFactory(factory):
            plugin = factory(self.wizard)
            return plugin.getConsumptionStep(type)

        def noBundle(failure):
            failure.trap(NoBundleError)

        d = self.wizard.getWizardEntry(componentType)
        d.addCallback(gotFactory)
        d.addErrback(noBundle)
        return d

    def getSteps(self):
        self._steplist = []
        for ctype in self._consumerTypes:
            if not self._buttons[ctype].get_active():
                continue
            for consumer, desc in self._consumers:
                if self._buttons[ctype+'-'+consumer].get_active():
                    d = self._loadStep(ctype, consumer)
                    yield d

    def getNext(self, step=None):
        if not self._stepsGen:
            self._stepsGen = self.getSteps()

        def addToList(newStep):
            self._steplist.append(newStep)
            return newStep

        if step in self._steplist and self._steplist[-1] != step:
            return self._steplist[self._steplist.index(step)+1]
        elif not step and self._steplist:
            return self._steplist[0]
        else:
            try:
                next = self._stepsGen.next()
                next.addCallback(addToList)
                return next
            except StopIteration:
                if not step:
                    return self._steplist[0]
                return

    # Private

    def _verify(self):
        blockNext = True

        elements = self._buttons

        def partials(ctype):
            if not elements[ctype].get_active():
                return False
            return pany([elements[ctype+'-'+consumer].get_active()
                         for consumer, _ in self._consumers])

        if reduce(bool.__or__, map(partials, self._consumerTypes)):
            blockNext = False

        self.wizard.blockNext(blockNext)

    def _canEmbedShout(self):
        encodingStep = self.wizard.getStep('Encoding')
        # Shoutcast supports only mp3 and ogg
        if (encodingStep.getAudioFormat() == 'mp3' or
            encodingStep.getMuxerFormat() == 'ogg'):
            return True
        return False

    # Callback

    def on_checkbutton_toggled(self, button, type):
        if type in self._consumerTypes:
            value = self._buttons[type].get_active()
            for key, desc in self._consumers:
                consumer = "%s-%s" % (type, key)
                self._buttons[consumer].set_sensitive(value)
                if self._hasBoth and key != 'audio-video':
                    continue
                if value:
                    self._buttons[consumer].set_active(value)

        self._verify()
        self._stepsGen = self.getSteps()
        self._steplist = []
